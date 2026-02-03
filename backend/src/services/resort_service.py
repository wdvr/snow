"""Resort management service."""

from typing import Any

from botocore.exceptions import ClientError

from models.resort import Resort

# Import directly from module to avoid circular import through utils/__init__.py
from utils.cache import get_resort_metadata_cache
from utils.dynamodb_utils import parse_from_dynamodb, prepare_for_dynamodb
from utils.geo_utils import (
    bounding_box,
    encode_geohash,
    get_geohashes_for_radius,
    haversine_distance,
)


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

    def get_nearby_resorts(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 200.0,
        limit: int = 20,
    ) -> list[tuple[Resort, float]]:
        """
        Get resorts near a given location, sorted by distance.

        Uses geohash-based indexing for efficient queries instead of full table scans.
        Falls back to table scan if geo_hash attribute is not present on resorts.

        Args:
            latitude: User's latitude in degrees
            longitude: User's longitude in degrees
            radius_km: Search radius in kilometers (default 200km)
            limit: Maximum number of results to return (default 20)

        Returns:
            List of tuples containing (Resort, distance_km), sorted by distance
        """
        try:
            # Determine geohash precision based on radius
            # Precision 4 = ~39km cells, good for up to ~100km radius
            # Precision 3 = ~156km cells, good for larger radii
            precision = 4 if radius_km <= 100 else 3

            # Get geohashes to query (center + 8 neighbors)
            geohashes = get_geohashes_for_radius(
                latitude, longitude, radius_km, precision
            )

            # Query GeoHashIndex for each geohash
            candidate_resorts = []
            seen_resort_ids = set()

            for geohash in geohashes:
                try:
                    response = self.table.query(
                        IndexName="GeoHashIndex",
                        KeyConditionExpression="geo_hash = :gh",
                        ExpressionAttributeValues={":gh": geohash},
                    )

                    for item in response.get("Items", []):
                        resort_id = item.get("resort_id")
                        if resort_id and resort_id not in seen_resort_ids:
                            seen_resort_ids.add(resort_id)
                            parsed_item = parse_from_dynamodb(item)
                            resort = Resort(**parsed_item)
                            candidate_resorts.append(resort)

                except ClientError:
                    # GeoHashIndex may not exist yet, fall back to scan
                    return self._get_nearby_resorts_scan(
                        latitude, longitude, radius_km, limit
                    )

            # If no results from geohash queries, fall back to scan
            # (handles case where resorts don't have geo_hash yet)
            if not candidate_resorts:
                return self._get_nearby_resorts_scan(
                    latitude, longitude, radius_km, limit
                )

            # Filter by exact distance using haversine
            min_lat, max_lat, min_lon, max_lon = bounding_box(
                latitude, longitude, radius_km
            )

            nearby = []
            for resort in candidate_resorts:
                coord = self._get_resort_coordinate(resort)
                if not coord:
                    continue

                resort_lat, resort_lon = coord

                # Quick bounding box check
                if not (
                    min_lat <= resort_lat <= max_lat
                    and min_lon <= resort_lon <= max_lon
                ):
                    continue

                # Calculate exact distance
                distance = haversine_distance(
                    latitude, longitude, resort_lat, resort_lon
                )

                if distance <= radius_km:
                    nearby.append((resort, round(distance, 1)))

            # Sort by distance and limit results
            nearby.sort(key=lambda x: x[1])
            return nearby[:limit]

        except Exception as e:
            raise Exception(f"Error finding nearby resorts: {str(e)}")

    def _get_nearby_resorts_scan(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
        limit: int,
    ) -> list[tuple[Resort, float]]:
        """
        Fallback method using full table scan for nearby resorts.

        Used when GeoHashIndex is not available or resorts lack geo_hash attribute.
        """
        all_resorts = self.get_all_resorts()

        min_lat, max_lat, min_lon, max_lon = bounding_box(
            latitude, longitude, radius_km
        )

        nearby = []
        for resort in all_resorts:
            coord = self._get_resort_coordinate(resort)
            if not coord:
                continue

            resort_lat, resort_lon = coord

            # Quick bounding box check
            if not (
                min_lat <= resort_lat <= max_lat and min_lon <= resort_lon <= max_lon
            ):
                continue

            # Calculate exact distance
            distance = haversine_distance(latitude, longitude, resort_lat, resort_lon)

            if distance <= radius_km:
                nearby.append((resort, round(distance, 1)))

        nearby.sort(key=lambda x: x[1])
        return nearby[:limit]

    def _get_resort_coordinate(self, resort: Resort) -> tuple[float, float] | None:
        """Get the primary coordinate for a resort (mid > base > first)."""
        # Prefer mid elevation for better representation of resort location
        if resort.mid_elevation:
            return (resort.mid_elevation.latitude, resort.mid_elevation.longitude)
        if resort.base_elevation:
            return (resort.base_elevation.latitude, resort.base_elevation.longitude)
        if resort.elevation_points:
            point = resort.elevation_points[0]
            return (point.latitude, point.longitude)
        return None

    def get_resort_names(self, resort_ids: list[str]) -> dict[str, str]:
        """
        Get resort names for multiple resort IDs efficiently.
        Uses cache with 24-hour TTL since resort names rarely change.

        Args:
            resort_ids: List of resort IDs

        Returns:
            Dict mapping resort_id -> resort_name
        """
        if not resort_ids:
            return {}

        cache = get_resort_metadata_cache()
        result = {}
        ids_to_fetch = []

        # Check cache first
        for resort_id in resort_ids:
            cache_key = f"name:{resort_id}"
            if cache_key in cache:
                result[resort_id] = cache[cache_key]
            else:
                ids_to_fetch.append(resort_id)

        # Batch fetch uncached resort names
        if ids_to_fetch:
            try:
                # DynamoDB batch_get_item can fetch up to 100 items
                for batch_start in range(0, len(ids_to_fetch), 100):
                    batch_ids = ids_to_fetch[batch_start : batch_start + 100]
                    keys = [{"resort_id": rid} for rid in batch_ids]

                    # Get table name for batch request
                    table_name = self.table.table_name
                    response = self.table.meta.client.batch_get_item(
                        RequestItems={
                            table_name: {
                                "Keys": keys,
                                "ProjectionExpression": "resort_id, #n",
                                "ExpressionAttributeNames": {"#n": "name"},
                            }
                        }
                    )

                    # Process results
                    items = response.get("Responses", {}).get(table_name, [])
                    for item in items:
                        resort_id = item.get("resort_id")
                        name = item.get("name", resort_id)
                        result[resort_id] = name
                        cache[f"name:{resort_id}"] = name

            except ClientError as e:
                # Fallback to individual gets on error
                for resort_id in ids_to_fetch:
                    try:
                        resort = self.get_resort(resort_id)
                        if resort:
                            result[resort_id] = resort.name
                            cache[f"name:{resort_id}"] = resort.name
                    except Exception:
                        result[resort_id] = resort_id

        # Fill in any missing names with resort_id as fallback
        for resort_id in resort_ids:
            if resort_id not in result:
                result[resort_id] = resort_id

        return result

    def compute_geohash_for_resort(
        self, resort: Resort, precision: int = 4
    ) -> str | None:
        """
        Compute geohash for a resort based on its primary coordinate.

        Args:
            resort: The resort to compute geohash for
            precision: Geohash precision (default 4 for ~39km cells)

        Returns:
            Geohash string or None if resort has no coordinates
        """
        coord = self._get_resort_coordinate(resort)
        if not coord:
            return None

        latitude, longitude = coord
        return encode_geohash(latitude, longitude, precision)

    def backfill_geohashes(self, precision: int = 4) -> dict[str, Any]:
        """
        Backfill geo_hash attribute for all existing resorts.

        This method should be run once after adding the GeoHashIndex GSI
        to populate the geo_hash field for existing resorts.

        Args:
            precision: Geohash precision (default 4 for ~39km cells)

        Returns:
            Dict with backfill statistics
        """
        stats = {
            "total_resorts": 0,
            "updated": 0,
            "skipped_no_coords": 0,
            "already_has_geohash": 0,
            "errors": 0,
        }

        try:
            # Scan all resorts
            response = self.table.scan()
            items = response.get("Items", [])

            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = self.table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                items.extend(response.get("Items", []))

            stats["total_resorts"] = len(items)

            for item in items:
                resort_id = item.get("resort_id")
                if not resort_id:
                    continue

                # Skip if already has geo_hash
                if item.get("geo_hash"):
                    stats["already_has_geohash"] += 1
                    continue

                try:
                    parsed_item = parse_from_dynamodb(item)
                    resort = Resort(**parsed_item)
                    geohash = self.compute_geohash_for_resort(resort, precision)

                    if not geohash:
                        stats["skipped_no_coords"] += 1
                        continue

                    # Update the resort with geo_hash
                    self.table.update_item(
                        Key={"resort_id": resort_id},
                        UpdateExpression="SET geo_hash = :gh",
                        ExpressionAttributeValues={":gh": geohash},
                    )
                    stats["updated"] += 1

                except Exception as e:
                    stats["errors"] += 1

            return stats

        except Exception as e:
            raise Exception(f"Error backfilling geohashes: {str(e)}")
