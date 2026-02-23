"""Streaming chat handler using Lambda Function URL with Lambda Web Adapter.

Uses FastAPI with StreamingResponse to return SSE events in real-time.
Lambda Web Adapter (LWA) bridges the Lambda runtime to the FastAPI HTTP server.

SSE event types:
- {"type":"status","message":"..."} - progress updates
- {"type":"tool_start","tool":"...","input":{}} - tool execution started
- {"type":"tool_done","tool":"...","duration_ms":123} - tool execution completed
- {"type":"text_delta","text":"..."} - streamed text chunk
- {"type":"done","conversation_id":"...","message_id":"..."} - completion
- {"type":"error","message":"..."} - error
"""

import json
import logging
import os
import queue
import threading
import time
import uuid

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from ulid import ULID

from services.chat_service import RESORT_ALIASES, SYSTEM_PROMPT, TOOL_DEFINITIONS

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BEDROCK_MAX_RETRIES = 3
BEDROCK_BASE_DELAY = 1.0
MAX_TOOL_ITERATIONS = 5

# Sentinel to signal end of stream
_STREAM_END = object()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


def _get_dynamodb():
    return boto3.resource(
        "dynamodb", region_name=os.environ.get("AWS_REGION_NAME", "us-west-2")
    )


def _get_bedrock():
    return boto3.client("bedrock-runtime", region_name="us-west-2")


def _validate_jwt(token: str) -> str | None:
    import jwt as pyjwt

    jwt_secret = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-in-prod")
    try:
        payload = pyjwt.decode(token, jwt_secret, algorithms=["HS256"])
        return payload.get("sub")
    except Exception:
        return None


@app.get("/")
async def health():
    return {"status": "ok"}


@app.post("/")
async def chat_stream(request: Request):
    """SSE streaming chat endpoint."""

    try:
        body = await request.json()
    except Exception:
        return StreamingResponse(
            iter([_sse({"type": "error", "message": "Invalid JSON"})]),
            media_type="text/event-stream",
        )

    user_message = body.get("message", "").strip()
    conversation_id = body.get("conversation_id")

    if not user_message:
        return StreamingResponse(
            iter([_sse({"type": "error", "message": "Message is required"})]),
            media_type="text/event-stream",
        )

    # Auth
    auth_header = request.headers.get("authorization", "")
    user_id = None
    if auth_header.startswith("Bearer "):
        user_id = _validate_jwt(auth_header[7:])
    if not user_id:
        user_id = f"anon_{request.client.host if request.client else 'unknown'}"

    # Use a thread-safe queue for the generator to yield from
    q: queue.Queue[str | object] = queue.Queue()

    def _produce():
        try:
            _handle_chat_stream(q, user_message, conversation_id, user_id)
        except Exception as e:
            logger.error("Stream handler error: %s", e, exc_info=True)
            q.put(_sse({"type": "error", "message": "Internal error"}))
        finally:
            q.put(_STREAM_END)

    # Run the producer in a background thread
    thread = threading.Thread(target=_produce, daemon=True)
    thread.start()

    def _generate():
        while True:
            item = q.get()
            if item is _STREAM_END:
                break
            yield item

    return StreamingResponse(_generate(), media_type="text/event-stream")


def _handle_chat_stream(q, user_message, conversation_id, user_id):
    """Main streaming chat logic. Writes SSE events to the queue."""
    q.put(_sse({"type": "status", "message": "Thinking..."}))

    dynamodb = _get_dynamodb()
    bedrock = _get_bedrock()
    chat_table_name = os.environ.get(
        "CHAT_TABLE_NAME", f"snow-tracker-chat-{os.environ.get('ENVIRONMENT', 'prod')}"
    )
    chat_table = dynamodb.Table(chat_table_name)

    if not conversation_id:
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

    history = _load_history(chat_table, conversation_id, user_id)
    messages = _build_messages(history, user_message)

    from datetime import UTC, datetime, timedelta

    user_message_id = str(ULID())
    now = datetime.now(UTC).isoformat()
    is_first = len(history) == 0
    title = user_message[:50] if is_first else None
    _save_message(
        chat_table,
        conversation_id,
        user_message_id,
        user_id,
        "user",
        user_message,
        now,
        title,
    )

    q.put(_sse({"type": "status", "message": "Analyzing your question..."}))
    context_data = _auto_detect_resorts_fast(user_message, dynamodb)

    system_text = SYSTEM_PROMPT
    if context_data:
        system_text += (
            "\n\n--- PRE-FETCHED DATA ---\n"
            "The following resort data was auto-detected from the user's message. "
            "Use this data directly instead of calling tools for these resorts. "
            "You may still use tools for additional resorts or data not covered here.\n\n"
            + context_data
        )
        q.put(_sse({"type": "status", "message": "Checking conditions..."}))

        text = _call_bedrock_stream_no_tools(bedrock, system_text, messages, q)
        if text:
            assistant_id = str(ULID())
            _save_message(
                chat_table,
                conversation_id,
                assistant_id,
                user_id,
                "assistant",
                text,
                datetime.now(UTC).isoformat(),
            )
            q.put(
                _sse(
                    {
                        "type": "done",
                        "conversation_id": conversation_id,
                        "message_id": assistant_id,
                    }
                )
            )
            return

    q.put(_sse({"type": "status", "message": "Looking up data..."}))
    text, tool_calls = _call_bedrock_with_tools_stream(
        bedrock, system_text, messages, q, dynamodb
    )

    assistant_id = str(ULID())
    _save_message(
        chat_table,
        conversation_id,
        assistant_id,
        user_id,
        "assistant",
        text,
        datetime.now(UTC).isoformat(),
        tool_calls=tool_calls,
    )

    q.put(
        _sse(
            {
                "type": "done",
                "conversation_id": conversation_id,
                "message_id": assistant_id,
            }
        )
    )


def _call_bedrock_stream_no_tools(bedrock, system_text, messages, q) -> str | None:
    try:
        response = bedrock.converse_stream(
            modelId="us.anthropic.claude-sonnet-4-6",
            system=[{"text": system_text}],
            messages=messages,
            inferenceConfig={"maxTokens": 2048, "temperature": 0.5},
        )

        stream = response.get("stream")
        if not stream:
            return None

        text_parts = []
        for event in stream:
            if "contentBlockDelta" in event:
                delta = event["contentBlockDelta"].get("delta", {})
                if "text" in delta:
                    chunk = delta["text"]
                    text_parts.append(chunk)
                    q.put(_sse({"type": "text_delta", "text": chunk}))

        return "".join(text_parts) if text_parts else None

    except Exception as e:
        logger.error("Bedrock stream error: %s", e)
        return None


def _call_bedrock_with_tools_stream(bedrock, system_text, messages, q, dynamodb):
    all_tool_calls = []

    for iteration in range(MAX_TOOL_ITERATIONS):
        t_bedrock = time.monotonic()
        try:
            response = bedrock.converse(
                modelId="us.anthropic.claude-sonnet-4-6",
                system=[{"text": system_text}],
                messages=messages,
                toolConfig={"tools": TOOL_DEFINITIONS},
                inferenceConfig={"maxTokens": 2048, "temperature": 0.5},
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if (
                error_code == "ThrottlingException"
                and iteration < BEDROCK_MAX_RETRIES - 1
            ):
                time.sleep(BEDROCK_BASE_DELAY * (2**iteration))
                continue
            q.put(_sse({"type": "error", "message": "AI service unavailable"}))
            return (
                "I'm having trouble connecting to the AI service. Please try again.",
                all_tool_calls or None,
            )
        except Exception as e:
            logger.error("Bedrock error: %s", e)
            return (
                "I'm having trouble connecting to the AI service. Please try again.",
                all_tool_calls or None,
            )

        bedrock_ms = int((time.monotonic() - t_bedrock) * 1000)
        logger.info("Bedrock call #%d took %dms", iteration + 1, bedrock_ms)

        output = response.get("output", {})
        message = output.get("message", {})
        content_blocks = message.get("content", [])
        stop_reason = response.get("stopReason", "end_turn")

        if stop_reason == "tool_use":
            tool_use_blocks = [b for b in content_blocks if "toolUse" in b]
            messages.append({"role": "assistant", "content": content_blocks})

            tool_results = []
            for tool_block in tool_use_blocks:
                tool_use = tool_block["toolUse"]
                tool_name = tool_use["name"]
                tool_input = tool_use.get("input", {})
                tool_use_id = tool_use["toolUseId"]

                friendly = _tool_friendly_name(tool_name, tool_input)
                q.put(
                    _sse(
                        {
                            "type": "tool_start",
                            "tool": tool_name,
                            "input": tool_input,
                            "message": friendly,
                        }
                    )
                )

                t_tool = time.monotonic()
                try:
                    result = _execute_tool(tool_name, tool_input, dynamodb)
                    tool_ms = int((time.monotonic() - t_tool) * 1000)
                    logger.info("Tool %s took %dms", tool_name, tool_ms)

                    q.put(
                        _sse(
                            {
                                "type": "tool_done",
                                "tool": tool_name,
                                "duration_ms": tool_ms,
                            }
                        )
                    )

                    all_tool_calls.append(
                        {
                            "tool": tool_name,
                            "input": tool_input,
                            "success": True,
                            "duration_ms": tool_ms,
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
                    tool_ms = int((time.monotonic() - t_tool) * 1000)
                    logger.error("Tool %s failed after %dms: %s", tool_name, tool_ms, e)
                    all_tool_calls.append(
                        {
                            "tool": tool_name,
                            "input": tool_input,
                            "success": False,
                            "duration_ms": tool_ms,
                        }
                    )
                    tool_results.append(
                        {
                            "toolResult": {
                                "toolUseId": tool_use_id,
                                "content": [{"text": f"Error: {e}"}],
                                "status": "error",
                            }
                        }
                    )

            messages.append({"role": "user", "content": tool_results})

            if iteration < MAX_TOOL_ITERATIONS - 1:
                try:
                    stream_resp = bedrock.converse_stream(
                        modelId="us.anthropic.claude-sonnet-4-6",
                        system=[{"text": system_text}],
                        messages=messages,
                        toolConfig={"tools": TOOL_DEFINITIONS},
                        inferenceConfig={"maxTokens": 2048, "temperature": 0.5},
                    )
                    stream = stream_resp.get("stream")
                    if stream:
                        text_parts = []
                        has_tool_use = False
                        for evt in stream:
                            if "contentBlockDelta" in evt:
                                delta = evt["contentBlockDelta"].get("delta", {})
                                if "text" in delta:
                                    chunk = delta["text"]
                                    text_parts.append(chunk)
                                    q.put(_sse({"type": "text_delta", "text": chunk}))
                            elif "contentBlockStart" in evt:
                                start = evt["contentBlockStart"].get("start", {})
                                if "toolUse" in start:
                                    has_tool_use = True
                                    break

                        if text_parts and not has_tool_use:
                            return "".join(text_parts), all_tool_calls or None

                        if has_tool_use:
                            continue
                except Exception as e:
                    logger.warning("Stream fallback: %s", e)

            continue

        # Final text response
        text_parts = [b["text"] for b in content_blocks if "text" in b]
        text = (
            "\n".join(text_parts) if text_parts else "I couldn't generate a response."
        )

        q.put(_sse({"type": "text_delta", "text": text}))
        return text, all_tool_calls or None

    return "I'm having trouble processing your request.", all_tool_calls or None


def _tool_friendly_name(tool_name: str, tool_input: dict) -> str:
    resort_id = tool_input.get("resort_id", "")
    resort_name = resort_id.replace("-", " ").title() if resort_id else ""

    names = {
        "get_resort_conditions": f"Checking conditions at {resort_name}..."
        if resort_name
        else "Checking conditions...",
        "search_resorts": f'Searching for "{tool_input.get("query", "")}"...',
        "get_nearby_resorts": "Finding nearby resorts...",
        "get_resort_forecast": f"Getting forecast for {resort_name}..."
        if resort_name
        else "Getting forecast...",
        "get_best_conditions": "Finding best conditions...",
        "get_resort_info": f"Looking up {resort_name}..."
        if resort_name
        else "Looking up resort info...",
        "get_condition_reports": f"Checking reports for {resort_name}..."
        if resort_name
        else "Checking reports...",
        "get_snow_history": f"Getting history for {resort_name}..."
        if resort_name
        else "Getting snow history...",
        "compare_resorts": "Comparing resorts...",
    }
    return names.get(tool_name, f"Running {tool_name}...")


def _auto_detect_resorts_fast(user_message: str, dynamodb) -> str | None:
    import re

    message_lower = user_message.lower()
    detected_ids: set[str] = set()

    for alias, resort_id in RESORT_ALIASES.items():
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, message_lower):
            detected_ids.add(resort_id)

    if not detected_ids:
        return None

    resort_ids = list(detected_ids)[:3]
    env = os.environ.get("ENVIRONMENT", "prod")
    conditions_table = dynamodb.Table(f"snow-tracker-weather-conditions-{env}")
    resorts_table = dynamodb.Table(f"snow-tracker-resorts-{env}")

    context_parts = []
    for resort_id in resort_ids:
        try:
            resort_resp = resorts_table.get_item(Key={"resort_id": resort_id})
            resort = resort_resp.get("Item", {})
            resort_name = resort.get("name", resort_id)

            cond_resp = conditions_table.query(
                KeyConditionExpression=Key("resort_id").eq(resort_id),
                ScanIndexForward=False,
                Limit=3,
            )
            conditions = cond_resp.get("Items", [])

            if conditions:
                elevations = {}
                for c in conditions:
                    level = c.get("elevation_level", "unknown")
                    elevations[level] = {
                        "temperature_celsius": _to_float(c.get("current_temp_celsius")),
                        "snowfall_24h_cm": _to_float(c.get("snowfall_24h_cm")),
                        "snow_quality": c.get("snow_quality", "unknown"),
                        "quality_score": _to_float(c.get("quality_score")),
                        "fresh_snow_cm": _to_float(c.get("fresh_snow_cm")),
                        "snow_depth_cm": _to_float(c.get("snow_depth_cm")),
                        "wind_speed_kmh": _to_float(c.get("wind_speed_kmh")),
                    }
                data = {"resort_id": resort_id, "elevations": elevations}
                context_parts.append(
                    f"Resort: {resort_name} ({resort_id})\n"
                    f"Conditions: {json.dumps(data, default=str)}\n"
                )
        except Exception as e:
            logger.warning("Auto-detect error for %s: %s", resort_id, e)

    return "\n".join(context_parts) if context_parts else None


def _to_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _execute_tool(tool_name: str, tool_input: dict, dynamodb) -> dict:
    env = os.environ.get("ENVIRONMENT", "prod")

    if tool_name == "get_resort_conditions":
        resort_id = tool_input.get("resort_id", "")
        if not resort_id:
            return {"error": "Missing resort_id"}
        table = dynamodb.Table(f"snow-tracker-weather-conditions-{env}")
        resp = table.query(
            KeyConditionExpression=Key("resort_id").eq(resort_id),
            ScanIndexForward=False,
            Limit=3,
        )
        items = resp.get("Items", [])
        if not items:
            return {"error": f"No conditions for '{resort_id}'"}
        elevations = {}
        for c in items:
            level = c.get("elevation_level", "unknown")
            elevations[level] = {
                "temperature_celsius": _to_float(c.get("current_temp_celsius")),
                "snowfall_24h_cm": _to_float(c.get("snowfall_24h_cm")),
                "snow_quality": c.get("snow_quality", "unknown"),
                "quality_score": _to_float(c.get("quality_score")),
                "fresh_snow_cm": _to_float(c.get("fresh_snow_cm")),
                "snow_depth_cm": _to_float(c.get("snow_depth_cm")),
                "wind_speed_kmh": _to_float(c.get("wind_speed_kmh")),
            }
        return {"resort_id": resort_id, "elevations": elevations}

    elif tool_name == "search_resorts":
        query_str = tool_input.get("query", "").lower()
        if not query_str:
            return {"error": "Missing query"}
        table = dynamodb.Table(f"snow-tracker-resorts-{env}")
        resp = table.scan()
        results = []
        for r in resp.get("Items", []):
            name = r.get("name", "").lower()
            region = r.get("region", "").lower()
            country = r.get("country", "").lower()
            if query_str in name or query_str in region or query_str in country:
                results.append(
                    {
                        "resort_id": r["resort_id"],
                        "name": r.get("name"),
                        "country": r.get("country"),
                        "region": r.get("region"),
                    }
                )
        return {"results": results[:20], "count": len(results)}

    elif tool_name == "get_best_conditions":
        try:
            s3 = boto3.client("s3", region_name="us-west-2")
            bucket = os.environ.get(
                "RESULTS_BUCKET", "snow-tracker-pulumi-state-us-west-2"
            )
            key = f"static-json/{env}/best-conditions.json"
            resp = s3.get_object(Bucket=bucket, Key=key)
            data = json.loads(resp["Body"].read())
            limit = min(tool_input.get("limit", 10), 20)
            return {"results": data[:limit], "count": len(data[:limit])}
        except Exception as e:
            logger.warning("Best conditions from S3 failed: %s", e)
            return {"error": "Could not fetch best conditions"}

    elif tool_name == "get_resort_info":
        resort_id = tool_input.get("resort_id", "")
        if not resort_id:
            return {"error": "Missing resort_id"}
        table = dynamodb.Table(f"snow-tracker-resorts-{env}")
        resp = table.get_item(Key={"resort_id": resort_id})
        item = resp.get("Item")
        if not item:
            return {"error": f"Resort '{resort_id}' not found"}
        return {
            "resort_id": item["resort_id"],
            "name": item.get("name"),
            "country": item.get("country"),
            "region": item.get("region"),
            "timezone": item.get("timezone"),
        }

    elif tool_name == "get_resort_forecast":
        resort_id = tool_input.get("resort_id", "")
        if not resort_id:
            return {"error": "Missing resort_id"}
        try:
            s3 = boto3.client("s3", region_name="us-west-2")
            bucket = os.environ.get(
                "RESULTS_BUCKET", "snow-tracker-pulumi-state-us-west-2"
            )
            key = f"static-json/{env}/resort-{resort_id}.json"
            resp = s3.get_object(Bucket=bucket, Key=key)
            data = json.loads(resp["Body"].read())
            return {"resort_id": resort_id, "forecast": data.get("forecast", data)}
        except Exception:
            return {"resort_id": resort_id, "forecast": "Not available"}

    elif tool_name == "get_snow_history":
        resort_id = tool_input.get("resort_id", "")
        if not resort_id:
            return {"error": "Missing resort_id"}
        table = dynamodb.Table(f"snow-tracker-daily-history-{env}")
        resp = table.query(
            KeyConditionExpression=Key("resort_id").eq(resort_id),
            ScanIndexForward=False,
            Limit=7,
        )
        items = resp.get("Items", [])
        items.reverse()
        total = sum(float(r.get("snowfall_24h_cm", 0)) for r in items)
        return {
            "resort_id": resort_id,
            "recent_days": [
                {
                    "date": r.get("date"),
                    "snowfall_24h_cm": _to_float(r.get("snowfall_24h_cm")),
                    "snow_depth_cm": _to_float(r.get("snow_depth_cm")),
                    "snow_quality": r.get("snow_quality"),
                }
                for r in items
            ],
            "total_snowfall_cm": round(total, 1),
        }

    elif tool_name == "get_condition_reports":
        resort_id = tool_input.get("resort_id", "")
        if not resort_id:
            return {"error": "Missing resort_id"}
        table = dynamodb.Table(f"snow-tracker-condition-reports-{env}")
        resp = table.query(
            KeyConditionExpression=Key("resort_id").eq(resort_id),
            ScanIndexForward=False,
            Limit=5,
        )
        items = resp.get("Items", [])
        return {
            "resort_id": resort_id,
            "reports": [
                {
                    "condition_type": r.get("condition_type"),
                    "score": _to_float(r.get("score")),
                    "comment": r.get("comment"),
                    "created_at": r.get("created_at"),
                }
                for r in items
            ],
        }

    elif tool_name == "compare_resorts":
        resort_ids = tool_input.get("resort_ids", [])
        if len(resort_ids) < 2:
            return {"error": "Need at least 2 resorts"}
        results = []
        for rid in resort_ids[:4]:
            cond = _execute_tool("get_resort_conditions", {"resort_id": rid}, dynamodb)
            results.append(cond)
        return {"comparison": results}

    elif tool_name == "get_nearby_resorts":
        lat = tool_input.get("latitude")
        lon = tool_input.get("longitude")
        if lat is None or lon is None:
            return {"error": "Missing coordinates"}
        import math

        table = dynamodb.Table(f"snow-tracker-resorts-{env}")
        resp = table.scan()
        items = resp.get("Items", [])
        nearby = []
        for r in items:
            eps = r.get("elevation_points", [])
            if not eps:
                continue
            ep = eps[0]
            rlat = float(ep.get("latitude", 0))
            rlon = float(ep.get("longitude", 0))
            dist = _haversine(lat, lon, rlat, rlon)
            radius = tool_input.get("radius_km", 200)
            if dist <= radius:
                nearby.append(
                    {
                        "resort_id": r["resort_id"],
                        "name": r.get("name"),
                        "country": r.get("country"),
                        "distance_km": round(dist, 1),
                    }
                )
        nearby.sort(key=lambda x: x["distance_km"])
        return {"results": nearby[:20], "count": len(nearby)}

    return {"error": f"Unknown tool: {tool_name}"}


def _haversine(lat1, lon1, lat2, lon2):
    import math

    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def _load_history(chat_table, conversation_id, user_id):
    try:
        resp = chat_table.query(
            KeyConditionExpression=Key("conversation_id").eq(conversation_id),
            ScanIndexForward=False,
            Limit=20,
        )
        items = resp.get("Items", [])
        if items and items[0].get("user_id") != user_id:
            return []
        items.reverse()
        return items
    except Exception:
        return []


def _build_messages(history, user_message):
    messages = []
    for item in history:
        role = item.get("role", "user")
        content = item.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": [{"text": content}]})
    messages.append({"role": "user", "content": [{"text": user_message}]})
    return messages


def _save_message(
    chat_table,
    conversation_id,
    message_id,
    user_id,
    role,
    content,
    created_at,
    title=None,
    tool_calls=None,
):
    from datetime import UTC, datetime, timedelta

    item = {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "created_at": created_at,
        "expires_at": int((datetime.now(UTC) + timedelta(days=30)).timestamp()),
    }
    if title:
        item["title"] = title
    if tool_calls:
        item["tool_calls"] = tool_calls
    try:
        chat_table.put_item(Item=item)
    except Exception as e:
        logger.error("Error saving message: %s", e)


# Lambda Web Adapter expects the app to listen on port 8080
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
