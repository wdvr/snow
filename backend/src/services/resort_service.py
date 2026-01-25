"""Resort management service."""

from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError

from models.resort import Resort

# Import directly from module to avoid circular import through utils/__init__.py
from utils.dynamodb_utils import parse_from_dynamodb, prepare_for_dynamodb


class ResortService:
    """Service for managing ski resort data."""

    def __init__(self, table):
        """Initialize the service with a DynamoDB table."""
        self.table = table

    def get_all_resorts(self) -> list[Resort]:
        """Get all resorts from the database."""
        try:
            response = self.table.scan()
            items = response.get("Items", [])

            resorts = []
            for item in items:
                # Convert DynamoDB Decimal types to Python native types
                parsed_item = parse_from_dynamodb(item)
                resort = Resort(**parsed_item)
                resorts.append(resort)

            return sorted(resorts, key=lambda r: r.name)

        except ClientError as e:
            raise Exception(f"Failed to retrieve resorts from database: {str(e)}")
        except Exception as e:
            raise Exception(f"Error processing resort data: {str(e)}")

    def get_resort(self, resort_id: str) -> Resort | None:
        """Get a specific resort by ID."""
        try:
            response = self.table.get_item(Key={"resort_id": resort_id})

            item = response.get("Item")
            if not item:
                return None

            # Convert DynamoDB Decimal types to Python native types
            parsed_item = parse_from_dynamodb(item)
            return Resort(**parsed_item)

        except ClientError as e:
            raise Exception(f"Failed to retrieve resort {resort_id}: {str(e)}")
        except Exception as e:
            raise Exception(f"Error processing resort data: {str(e)}")

    def create_resort(self, resort: Resort) -> Resort:
        """Create a new resort."""
        try:
            # Convert resort to DynamoDB item format
            item = resort.model_dump()

            # Convert enum values to strings
            for point in item.get("elevation_points", []):
                if "level" in point and hasattr(point["level"], "value"):
                    point["level"] = point["level"].value

            # Convert Python types to DynamoDB Decimal types
            item = prepare_for_dynamodb(item)

            self.table.put_item(
                Item=item, ConditionExpression="attribute_not_exists(resort_id)"
            )

            return resort

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise Exception(f"Resort {resort.resort_id} already exists")
            else:
                raise Exception(f"Failed to create resort: {str(e)}")
        except Exception as e:
            raise Exception(f"Error creating resort: {str(e)}")

    def update_resort(self, resort: Resort) -> Resort:
        """Update an existing resort."""
        try:
            # Convert resort to DynamoDB item format
            item = resort.model_dump()

            # Convert enum values to strings
            for point in item.get("elevation_points", []):
                if "level" in point and hasattr(point["level"], "value"):
                    point["level"] = point["level"].value

            # Convert Python types to DynamoDB Decimal types
            item = prepare_for_dynamodb(item)

            self.table.put_item(
                Item=item, ConditionExpression="attribute_exists(resort_id)"
            )

            return resort

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise Exception(f"Resort {resort.resort_id} does not exist")
            else:
                raise Exception(f"Failed to update resort: {str(e)}")
        except Exception as e:
            raise Exception(f"Error updating resort: {str(e)}")

    def delete_resort(self, resort_id: str) -> bool:
        """Delete a resort."""
        try:
            self.table.delete_item(
                Key={"resort_id": resort_id},
                ConditionExpression="attribute_exists(resort_id)",
            )

            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise Exception(f"Resort {resort_id} does not exist")
            else:
                raise Exception(f"Failed to delete resort: {str(e)}")
        except Exception as e:
            raise Exception(f"Error deleting resort: {str(e)}")

    def get_resorts_by_country(self, country: str) -> list[Resort]:
        """Get resorts filtered by country."""
        try:
            response = self.table.query(
                IndexName="CountryIndex",
                KeyConditionExpression="country = :country",
                ExpressionAttributeValues={":country": country.upper()},
            )

            items = response.get("Items", [])
            resorts = []

            for item in items:
                # Convert DynamoDB Decimal types to Python native types
                parsed_item = parse_from_dynamodb(item)
                resort = Resort(**parsed_item)
                resorts.append(resort)

            return sorted(resorts, key=lambda r: r.name)

        except ClientError as e:
            raise Exception(
                f"Failed to retrieve resorts for country {country}: {str(e)}"
            )
        except Exception as e:
            raise Exception(f"Error processing resort data: {str(e)}")

    def search_resorts(self, query: str) -> list[Resort]:
        """Search resorts by name or region."""
        try:
            # Get all resorts and filter in memory
            # For production, consider using DynamoDB's full-text search capabilities
            all_resorts = self.get_all_resorts()

            query_lower = query.lower()
            filtered_resorts = []

            for resort in all_resorts:
                if (
                    query_lower in resort.name.lower()
                    or query_lower in resort.region.lower()
                    or query_lower in resort.country.lower()
                ):
                    filtered_resorts.append(resort)

            return filtered_resorts

        except Exception as e:
            raise Exception(f"Error searching resorts: {str(e)}")

    def get_resort_statistics(self) -> dict[str, Any]:
        """Get statistics about resorts in the system."""
        try:
            resorts = self.get_all_resorts()

            # Calculate statistics
            countries = {}
            total_elevation_points = 0

            for resort in resorts:
                country = resort.country
                if country in countries:
                    countries[country] += 1
                else:
                    countries[country] = 1

                total_elevation_points += len(resort.elevation_points)

            return {
                "total_resorts": len(resorts),
                "resorts_by_country": countries,
                "total_elevation_points": total_elevation_points,
                "average_elevation_points_per_resort": (
                    total_elevation_points / len(resorts) if resorts else 0
                ),
            }

        except Exception as e:
            raise Exception(f"Error calculating resort statistics: {str(e)}")
