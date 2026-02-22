"""AI chat service using AWS Bedrock with tool use for ski conditions."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from ulid import ULID

from models.chat import ChatMessage, ChatResponse, ConversationSummary

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are Powder Chaser AI, a knowledgeable ski conditions assistant. "
    "You help skiers find the best conditions using real-time resort data. "
    "Keep responses concise and actionable. Use tools to fetch current data — "
    "never guess conditions. Only answer ski/snow related questions."
)

TOOL_DEFINITIONS = [
    {
        "toolSpec": {
            "name": "get_resort_conditions",
            "description": "Get current weather conditions for a resort at all elevations.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "resort_id": {
                            "type": "string",
                            "description": "The resort identifier (e.g. 'big-white', 'whistler-blackcomb')",
                        }
                    },
                    "required": ["resort_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "search_resorts",
            "description": "Search resorts by name, region, or country.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (resort name, region, or country)",
                        }
                    },
                    "required": ["query"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_nearby_resorts",
            "description": "Find resorts near given coordinates.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "latitude": {
                            "type": "number",
                            "description": "Latitude in degrees",
                        },
                        "longitude": {
                            "type": "number",
                            "description": "Longitude in degrees",
                        },
                        "radius_km": {
                            "type": "number",
                            "description": "Search radius in kilometers (default 200)",
                        },
                    },
                    "required": ["latitude", "longitude"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_resort_forecast",
            "description": "Get 7-day timeline forecast for a resort.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "resort_id": {
                            "type": "string",
                            "description": "The resort identifier",
                        }
                    },
                    "required": ["resort_id"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_best_conditions",
            "description": "Get top resorts by current snow quality globally.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Number of results (default 10)",
                        }
                    },
                    "required": [],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_resort_info",
            "description": "Get resort metadata including elevation, location, and URL.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "resort_id": {
                            "type": "string",
                            "description": "The resort identifier",
                        }
                    },
                    "required": ["resort_id"],
                }
            },
        }
    },
]

# Max tool use iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 5

# TTL for chat messages: 30 days
MESSAGE_TTL_DAYS = 30


class ChatService:
    """Service for AI-powered ski conditions chat using AWS Bedrock."""

    def __init__(
        self,
        chat_table,
        resort_service,
        weather_service,
        snow_quality_service,
        recommendation_service,
    ):
        """Initialize the chat service.

        Args:
            chat_table: DynamoDB table for conversation storage
            resort_service: ResortService for resort data
            weather_service: WeatherService for conditions data
            snow_quality_service: SnowQualityService for quality assessment
            recommendation_service: RecommendationService for best conditions
        """
        self.chat_table = chat_table
        self.resort_service = resort_service
        self.weather_service = weather_service
        self.snow_quality_service = snow_quality_service
        self.recommendation_service = recommendation_service
        self.bedrock = boto3.client("bedrock-runtime", region_name="us-west-2")

    def chat(
        self, user_message: str, conversation_id: str | None, user_id: str
    ) -> ChatResponse:
        """Process a chat message and return an AI response.

        Args:
            user_message: The user's message text
            conversation_id: Existing conversation ID or None for new conversation
            user_id: The authenticated user's ID

        Returns:
            ChatResponse with conversation_id, response text, and message_id
        """
        # Generate conversation_id if new
        if not conversation_id:
            conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

        # Load conversation history (last 20 messages)
        history = self._load_history(conversation_id, user_id)

        # Build messages for Bedrock
        messages = self._build_messages(history, user_message)

        # Save user message
        user_message_id = str(ULID())
        now = datetime.now(UTC).isoformat()
        is_first_message = len(history) == 0
        title = self._generate_title(user_message) if is_first_message else None

        self._save_message(
            conversation_id=conversation_id,
            message_id=user_message_id,
            user_id=user_id,
            role="user",
            content=user_message,
            created_at=now,
            title=title,
        )

        # Call Bedrock with tool use loop
        assistant_text, tool_calls = self._call_bedrock_with_tools(messages)

        # Save assistant message
        assistant_message_id = str(ULID())
        assistant_now = datetime.now(UTC).isoformat()

        self._save_message(
            conversation_id=conversation_id,
            message_id=assistant_message_id,
            user_id=user_id,
            role="assistant",
            content=assistant_text,
            created_at=assistant_now,
            tool_calls=tool_calls if tool_calls else None,
        )

        return ChatResponse(
            conversation_id=conversation_id,
            response=assistant_text,
            message_id=assistant_message_id,
        )

    def list_conversations(self, user_id: str) -> list[ConversationSummary]:
        """List all conversations for a user.

        Args:
            user_id: The user's ID

        Returns:
            List of ConversationSummary objects sorted by last_message_at descending
        """
        try:
            response = self.chat_table.query(
                IndexName="UserIndex",
                KeyConditionExpression=Key("user_id").eq(user_id),
                ScanIndexForward=False,
            )

            items = response.get("Items", [])

            # Group by conversation_id to build summaries
            conversations: dict[str, dict[str, Any]] = {}
            for item in items:
                conv_id = item.get("conversation_id")
                if not conv_id:
                    continue

                if conv_id not in conversations:
                    conversations[conv_id] = {
                        "conversation_id": conv_id,
                        "title": item.get("title", ""),
                        "last_message_at": item.get("created_at", ""),
                        "message_count": 0,
                    }

                conversations[conv_id]["message_count"] += 1

                # Update title if this item has one (first message has the title)
                if item.get("title") and not conversations[conv_id]["title"]:
                    conversations[conv_id]["title"] = item["title"]

                # Update last_message_at to the latest
                if (
                    item.get("created_at", "")
                    > conversations[conv_id]["last_message_at"]
                ):
                    conversations[conv_id]["last_message_at"] = item["created_at"]

            # Convert to ConversationSummary and sort by last_message_at
            summaries = []
            for conv_data in conversations.values():
                summaries.append(
                    ConversationSummary(
                        conversation_id=conv_data["conversation_id"],
                        title=conv_data["title"] or "Untitled",
                        last_message_at=conv_data["last_message_at"],
                        message_count=conv_data["message_count"],
                    )
                )

            summaries.sort(key=lambda s: s.last_message_at, reverse=True)
            return summaries

        except Exception as e:
            logger.error("Error listing conversations for user %s: %s", user_id, e)
            return []

    def get_conversation(self, conversation_id: str, user_id: str) -> list[ChatMessage]:
        """Get all messages in a conversation.

        Args:
            conversation_id: The conversation ID
            user_id: The user's ID (for ownership verification)

        Returns:
            List of ChatMessage objects sorted by created_at ascending

        Raises:
            ValueError: If conversation not found or user doesn't own it
        """
        try:
            response = self.chat_table.query(
                KeyConditionExpression=Key("conversation_id").eq(conversation_id),
                ScanIndexForward=True,  # Oldest first
            )

            items = response.get("Items", [])

            if not items:
                raise ValueError("Conversation not found")

            # Verify ownership
            if items[0].get("user_id") != user_id:
                raise ValueError("Conversation not found")

            messages = []
            for item in items:
                messages.append(
                    ChatMessage(
                        role=item.get("role", "user"),
                        content=item.get("content", ""),
                        message_id=item.get("message_id", ""),
                        created_at=item.get("created_at", ""),
                        tool_calls=item.get("tool_calls"),
                    )
                )

            return messages

        except ValueError:
            raise
        except Exception as e:
            logger.error("Error getting conversation %s: %s", conversation_id, e)
            raise ValueError("Conversation not found")

    def delete_conversation(self, conversation_id: str, user_id: str) -> None:
        """Delete all messages in a conversation.

        Args:
            conversation_id: The conversation ID
            user_id: The user's ID (for ownership verification)

        Raises:
            ValueError: If conversation not found or user doesn't own it
        """
        try:
            # Get all messages in the conversation
            response = self.chat_table.query(
                KeyConditionExpression=Key("conversation_id").eq(conversation_id),
                ProjectionExpression="conversation_id, message_id, user_id",
            )

            items = response.get("Items", [])
            if not items:
                raise ValueError("Conversation not found")

            # Verify ownership
            if items[0].get("user_id") != user_id:
                raise ValueError("Conversation not found")

            # Delete all messages
            with self.chat_table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(
                        Key={
                            "conversation_id": item["conversation_id"],
                            "message_id": item["message_id"],
                        }
                    )

        except ValueError:
            raise
        except Exception as e:
            logger.error("Error deleting conversation %s: %s", conversation_id, e)
            raise ValueError("Failed to delete conversation")

    # ---- Private methods ----

    def _load_history(self, conversation_id: str, user_id: str) -> list[dict[str, Any]]:
        """Load last 20 messages from a conversation."""
        try:
            response = self.chat_table.query(
                KeyConditionExpression=Key("conversation_id").eq(conversation_id),
                ScanIndexForward=False,  # Most recent first
                Limit=20,
            )

            items = response.get("Items", [])

            # Verify ownership if messages exist
            if items and items[0].get("user_id") != user_id:
                return []

            # Reverse to chronological order
            items.reverse()
            return items

        except Exception as e:
            logger.error(
                "Error loading history for conversation %s: %s",
                conversation_id,
                e,
            )
            return []

    def _build_messages(
        self, history: list[dict[str, Any]], user_message: str
    ) -> list[dict]:
        """Build the messages array for Bedrock converse API."""
        messages = []

        for item in history:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": [{"text": content}]})

        # Add the new user message
        messages.append({"role": "user", "content": [{"text": user_message}]})

        return messages

    def _call_bedrock_with_tools(
        self, messages: list[dict]
    ) -> tuple[str, list[dict[str, Any]] | None]:
        """Call Bedrock converse API with tool use loop.

        Returns:
            Tuple of (assistant_text, tool_calls_list)
        """
        all_tool_calls = []

        for _iteration in range(MAX_TOOL_ITERATIONS):
            response = self.bedrock.converse(
                modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
                system=[{"text": SYSTEM_PROMPT}],
                messages=messages,
                toolConfig={"tools": TOOL_DEFINITIONS},
                inferenceConfig={"maxTokens": 1024, "temperature": 0.3},
            )

            # Extract the response
            output = response.get("output", {})
            message = output.get("message", {})
            content_blocks = message.get("content", [])
            stop_reason = response.get("stopReason", "end_turn")

            # Check if there are tool use requests
            if stop_reason == "tool_use":
                # Process tool calls
                tool_use_blocks = [b for b in content_blocks if "toolUse" in b]
                text_blocks = [b for b in content_blocks if "text" in b]

                # Add assistant message with tool use to conversation
                messages.append({"role": "assistant", "content": content_blocks})

                # Execute tools and build result message
                tool_results = []
                for tool_block in tool_use_blocks:
                    tool_use = tool_block["toolUse"]
                    tool_name = tool_use["name"]
                    tool_input = tool_use.get("input", {})
                    tool_use_id = tool_use["toolUseId"]

                    logger.info(
                        "Executing tool: %s with input: %s", tool_name, tool_input
                    )

                    try:
                        result = self._execute_tool(tool_name, tool_input)
                        all_tool_calls.append(
                            {
                                "tool": tool_name,
                                "input": tool_input,
                                "success": True,
                            }
                        )
                        tool_results.append(
                            {
                                "toolResult": {
                                    "toolUseId": tool_use_id,
                                    "content": [{"json": result}],
                                }
                            }
                        )
                    except Exception as e:
                        logger.error("Tool execution error for %s: %s", tool_name, e)
                        all_tool_calls.append(
                            {
                                "tool": tool_name,
                                "input": tool_input,
                                "success": False,
                                "error": str(e),
                            }
                        )
                        tool_results.append(
                            {
                                "toolResult": {
                                    "toolUseId": tool_use_id,
                                    "content": [{"text": f"Error: {str(e)}"}],
                                    "status": "error",
                                }
                            }
                        )

                # Add tool results as user message
                messages.append({"role": "user", "content": tool_results})
                continue

            # No tool use - extract final text response
            text_parts = []
            for block in content_blocks:
                if "text" in block:
                    text_parts.append(block["text"])

            assistant_text = (
                "\n".join(text_parts)
                if text_parts
                else "I couldn't generate a response. Please try again."
            )
            return assistant_text, all_tool_calls if all_tool_calls else None

        # Exhausted iterations
        return (
            "I'm having trouble processing your request. Please try a simpler question.",
            all_tool_calls if all_tool_calls else None,
        )

    def _execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        """Execute a tool and return the result as a dictionary."""
        if tool_name == "get_resort_conditions":
            return self._tool_get_resort_conditions(tool_input["resort_id"])
        elif tool_name == "search_resorts":
            return self._tool_search_resorts(tool_input["query"])
        elif tool_name == "get_nearby_resorts":
            return self._tool_get_nearby_resorts(
                tool_input["latitude"],
                tool_input["longitude"],
                tool_input.get("radius_km", 200),
            )
        elif tool_name == "get_resort_forecast":
            return self._tool_get_resort_forecast(tool_input["resort_id"])
        elif tool_name == "get_best_conditions":
            return self._tool_get_best_conditions(tool_input.get("limit", 10))
        elif tool_name == "get_resort_info":
            return self._tool_get_resort_info(tool_input["resort_id"])
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _tool_get_resort_conditions(self, resort_id: str) -> dict:
        """Get current conditions for a resort at all elevations."""
        conditions = self.weather_service.get_conditions_for_resort(resort_id)
        if not conditions:
            return {"error": f"No conditions data available for resort '{resort_id}'."}

        result = {"resort_id": resort_id, "elevations": {}}
        for c in conditions:
            quality_val = (
                c.snow_quality.value
                if hasattr(c.snow_quality, "value")
                else str(c.snow_quality)
            )
            result["elevations"][c.elevation_level] = {
                "temperature_celsius": c.current_temp_celsius,
                "snowfall_24h_cm": c.snowfall_24h_cm,
                "snowfall_72h_cm": c.snowfall_72h_cm,
                "snow_quality": quality_val,
                "fresh_snow_cm": c.fresh_snow_cm,
                "wind_speed_kmh": c.wind_speed_kmh,
                "weather_description": c.weather_description,
            }
        return result

    def _tool_search_resorts(self, query: str) -> dict:
        """Search resorts by name, region, or country."""
        resorts = self.resort_service.search_resorts(query)
        return {
            "results": [
                {
                    "resort_id": r.resort_id,
                    "name": r.name,
                    "country": r.country,
                    "region": r.region,
                }
                for r in resorts[:20]  # Limit results
            ],
            "count": len(resorts),
        }

    def _tool_get_nearby_resorts(
        self, latitude: float, longitude: float, radius_km: float
    ) -> dict:
        """Find resorts near given coordinates."""
        nearby = self.resort_service.get_nearby_resorts(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=20,
        )
        return {
            "results": [
                {
                    "resort_id": resort.resort_id,
                    "name": resort.name,
                    "country": resort.country,
                    "distance_km": distance,
                }
                for resort, distance in nearby
            ],
            "count": len(nearby),
        }

    def _tool_get_resort_forecast(self, resort_id: str) -> dict:
        """Get 7-day forecast for a resort."""
        from services.openmeteo_service import OpenMeteoService

        resort = self.resort_service.get_resort(resort_id)
        if not resort:
            return {"error": f"Resort '{resort_id}' not found."}

        # Use mid elevation for forecast (preferred)
        ep = resort.mid_elevation or resort.base_elevation
        if not ep and resort.elevation_points:
            ep = resort.elevation_points[0]
        if not ep:
            return {"error": f"No elevation data for resort '{resort_id}'."}

        try:
            service = OpenMeteoService()
            timeline = service.get_timeline_data(
                latitude=ep.latitude,
                longitude=ep.longitude,
                elevation_meters=ep.elevation_meters,
                elevation_level=ep.level
                if hasattr(ep.level, "value")
                else str(ep.level),
            )
            # Summarize for the AI (full timeline is too large)
            data_points = timeline.get("data", [])
            summary = {
                "resort_id": resort_id,
                "resort_name": resort.name,
                "elevation_level": str(ep.level),
                "days": [],
            }
            # Group by date and take daily summaries
            daily: dict[str, list] = {}
            for dp in data_points:
                date = dp.get("date", "")
                if date not in daily:
                    daily[date] = []
                daily[date].append(dp)

            for date, points in sorted(daily.items())[:7]:
                temps = [
                    p.get("temperature_c", 0)
                    for p in points
                    if p.get("temperature_c") is not None
                ]
                snowfall = sum(p.get("snowfall_cm", 0) for p in points)
                summary["days"].append(
                    {
                        "date": date,
                        "min_temp_c": min(temps) if temps else None,
                        "max_temp_c": max(temps) if temps else None,
                        "total_snowfall_cm": round(snowfall, 1),
                    }
                )
            return summary
        except Exception as e:
            logger.error("Forecast error for %s: %s", resort_id, e)
            return {"error": f"Could not fetch forecast for '{resort_id}'."}

    def _tool_get_best_conditions(self, limit: int) -> dict:
        """Get top resorts by current snow quality."""
        try:
            recommendations = self.recommendation_service.get_best_conditions_globally(
                limit=min(limit, 20),
            )
            return {
                "results": [
                    {
                        "resort_id": r.resort.resort_id,
                        "resort_name": r.resort.name,
                        "country": r.resort.country,
                        "snow_quality": r.snow_quality.value
                        if hasattr(r.snow_quality, "value")
                        else str(r.snow_quality),
                        "fresh_snow_cm": r.fresh_snow_cm,
                        "temperature_celsius": r.current_temp_celsius,
                        "reason": r.reason,
                    }
                    for r in recommendations
                ],
                "count": len(recommendations),
            }
        except Exception as e:
            logger.error("Best conditions error: %s", e)
            return {"error": "Could not fetch best conditions."}

    def _tool_get_resort_info(self, resort_id: str) -> dict:
        """Get resort metadata."""
        resort = self.resort_service.get_resort(resort_id)
        if not resort:
            return {"error": f"Resort '{resort_id}' not found."}

        elevations = {}
        for ep in resort.elevation_points:
            level = ep.level if isinstance(ep.level, str) else ep.level
            elevations[str(level)] = {
                "elevation_meters": ep.elevation_meters,
                "elevation_feet": ep.elevation_feet,
                "latitude": ep.latitude,
                "longitude": ep.longitude,
            }

        return {
            "resort_id": resort.resort_id,
            "name": resort.name,
            "country": resort.country,
            "region": resort.region,
            "timezone": resort.timezone,
            "official_website": resort.official_website,
            "elevation_points": elevations,
        }

    def _save_message(
        self,
        conversation_id: str,
        message_id: str,
        user_id: str,
        role: str,
        content: str,
        created_at: str,
        title: str | None = None,
        tool_calls: list[dict] | None = None,
    ) -> None:
        """Save a message to DynamoDB."""
        expires_at = int(
            (datetime.now(UTC) + timedelta(days=MESSAGE_TTL_DAYS)).timestamp()
        )

        item: dict[str, Any] = {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "created_at": created_at,
            "expires_at": expires_at,
        }

        if title:
            item["title"] = title

        if tool_calls:
            item["tool_calls"] = tool_calls

        try:
            self.chat_table.put_item(Item=item)
        except Exception as e:
            logger.error("Error saving message %s: %s", message_id, e)

    def _generate_title(self, first_message: str) -> str:
        """Generate a conversation title from the first user message."""
        # Use first sentence or first 50 characters
        for sep in (".", "?", "!"):
            idx = first_message.find(sep)
            if 0 < idx <= 50:
                return first_message[: idx + 1]

        if len(first_message) <= 50:
            return first_message

        # Truncate at word boundary
        truncated = first_message[:50]
        last_space = truncated.rfind(" ")
        if last_space > 20:
            return truncated[:last_space] + "..."
        return truncated + "..."
