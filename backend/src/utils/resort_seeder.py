"""Resort data seeder for populating initial ski resort data."""

import json
import logging
from datetime import UTC, datetime, timezone
from typing import Any, Dict, List

from models.resort import ElevationLevel, ElevationPoint, Resort
from services.resort_service import ResortService

logger = logging.getLogger(__name__)


class ResortSeeder:
    """Service for seeding initial resort data into the database."""

    def __init__(self, resort_service: ResortService):
        """Initialize the seeder with a resort service."""
        self.resort_service = resort_service

    def seed_initial_resorts(self) -> dict[str, Any]:
        """
        Seed the initial three resorts: Big White, Lake Louise, Silver Star.

        Returns:
            Dictionary with seeding results and statistics.
        """
        logger.info("Starting resort data seeding...")

        results = {
            "resorts_created": 0,
            "resorts_skipped": 0,
            "errors": [],
            "created_resorts": [],
        }

        initial_resorts = self._get_initial_resort_data()

        for resort_data in initial_resorts:
            try:
                # Check if resort already exists
                existing = self.resort_service.get_resort(resort_data.resort_id)
                if existing:
                    logger.info(
                        f"Resort {resort_data.resort_id} already exists, skipping"
                    )
                    results["resorts_skipped"] += 1
                    continue

                # Create the resort
                created_resort = self.resort_service.create_resort(resort_data)
                logger.info(f"Successfully created resort: {created_resort.name}")

                results["resorts_created"] += 1
                results["created_resorts"].append(created_resort.resort_id)

            except Exception as e:
                error_msg = f"Failed to create resort {resort_data.resort_id}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        logger.info(
            f"Resort seeding completed. Created: {results['resorts_created']}, "
            f"Skipped: {results['resorts_skipped']}, Errors: {len(results['errors'])}"
        )

        return results

    def _get_initial_resort_data(self) -> list[Resort]:
        """Get the initial resort data with accurate coordinates and elevations."""
        now = datetime.now(UTC).isoformat()

        return [
            Resort(
                resort_id="big-white",
                name="Big White Ski Resort",
                country="CA",
                region="BC",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=1508,
                        elevation_feet=4950,
                        latitude=49.719628,  # Gem Lake Base coordinates
                        longitude=-118.929579,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=1755,
                        elevation_feet=5757,
                        latitude=49.721628,  # Village Centre coordinates
                        longitude=-118.926579,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=2319,
                        elevation_feet=7608,
                        latitude=49.723628,  # Summit coordinates
                        longitude=-118.923579,
                        weather_station_id=None,
                    ),
                ],
                timezone="America/Vancouver",
                official_website="https://www.bigwhite.com",
                weather_sources=["weatherapi", "snow-report"],
                created_at=now,
                updated_at=now,
            ),
            Resort(
                resort_id="lake-louise",
                name="Lake Louise Ski Resort",
                country="CA",
                region="AB",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=1646,
                        elevation_feet=5400,
                        latitude=51.439921,  # Base lodge coordinates
                        longitude=-116.165172,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=2100,
                        elevation_feet=6890,
                        latitude=51.441921,  # Mid-mountain coordinates
                        longitude=-116.162172,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=2637,
                        elevation_feet=8652,
                        latitude=51.443921,  # Mt. Whitehorn summit coordinates
                        longitude=-116.159172,
                        weather_station_id=None,
                    ),
                ],
                timezone="America/Edmonton",
                official_website="https://www.skilouise.com",
                weather_sources=["weatherapi", "snow-report"],
                created_at=now,
                updated_at=now,
            ),
            Resort(
                resort_id="silver-star",
                name="SilverStar Mountain Resort",
                country="CA",
                region="BC",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=1155,
                        elevation_feet=3790,
                        latitude=50.356390,  # Base village coordinates
                        longitude=-119.067410,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=1609,
                        elevation_feet=5279,
                        latitude=50.358390,  # Mid-mountain village coordinates
                        longitude=-119.064410,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=1915,
                        elevation_feet=6283,
                        latitude=50.360390,  # Summit coordinates
                        longitude=-119.061410,
                        weather_station_id=None,
                    ),
                ],
                timezone="America/Vancouver",
                official_website="https://www.skisilverstar.com",
                weather_sources=["weatherapi", "snow-report"],
                created_at=now,
                updated_at=now,
            ),
            # ===== US RESORTS =====
            Resort(
                resort_id="vail",
                name="Vail Mountain Resort",
                country="US",
                region="CO",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=2475,
                        elevation_feet=8120,
                        latitude=39.640259,
                        longitude=-106.374187,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=3231,
                        elevation_feet=10600,
                        latitude=39.622259,
                        longitude=-106.380187,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=3527,
                        elevation_feet=11570,
                        latitude=39.605259,
                        longitude=-106.385187,
                        weather_station_id=None,
                    ),
                ],
                timezone="America/Denver",
                official_website="https://www.vail.com",
                weather_sources=["weatherapi"],
                created_at=now,
                updated_at=now,
            ),
            Resort(
                resort_id="park-city",
                name="Park City Mountain Resort",
                country="US",
                region="UT",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=2103,
                        elevation_feet=6900,
                        latitude=40.651333,
                        longitude=-111.507883,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=2591,
                        elevation_feet=8500,
                        latitude=40.640333,
                        longitude=-111.515883,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=3048,
                        elevation_feet=10000,
                        latitude=40.630333,
                        longitude=-111.523883,
                        weather_station_id=None,
                    ),
                ],
                timezone="America/Denver",
                official_website="https://www.parkcitymountain.com",
                weather_sources=["weatherapi"],
                created_at=now,
                updated_at=now,
            ),
            Resort(
                resort_id="mammoth-mountain",
                name="Mammoth Mountain",
                country="US",
                region="CA",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=2424,
                        elevation_feet=7953,
                        latitude=37.630719,
                        longitude=-119.032579,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=2987,
                        elevation_feet=9800,
                        latitude=37.638719,
                        longitude=-119.037579,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=3369,
                        elevation_feet=11053,
                        latitude=37.643719,
                        longitude=-119.042579,
                        weather_station_id=None,
                    ),
                ],
                timezone="America/Los_Angeles",
                official_website="https://www.mammothmountain.com",
                weather_sources=["weatherapi"],
                created_at=now,
                updated_at=now,
            ),
            Resort(
                resort_id="jackson-hole",
                name="Jackson Hole Mountain Resort",
                country="US",
                region="WY",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=1924,
                        elevation_feet=6311,
                        latitude=43.587593,
                        longitude=-110.827682,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=2591,
                        elevation_feet=8500,
                        latitude=43.594593,
                        longitude=-110.837682,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=3185,
                        elevation_feet=10450,
                        latitude=43.601593,
                        longitude=-110.847682,
                        weather_station_id=None,
                    ),
                ],
                timezone="America/Denver",
                official_website="https://www.jacksonhole.com",
                weather_sources=["weatherapi"],
                created_at=now,
                updated_at=now,
            ),
            Resort(
                resort_id="aspen-snowmass",
                name="Aspen Snowmass",
                country="US",
                region="CO",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=2473,
                        elevation_feet=8114,
                        latitude=39.212879,
                        longitude=-106.949802,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=3231,
                        elevation_feet=10600,
                        latitude=39.206879,
                        longitude=-106.958802,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=3813,
                        elevation_feet=12510,
                        latitude=39.198879,
                        longitude=-106.968802,
                        weather_station_id=None,
                    ),
                ],
                timezone="America/Denver",
                official_website="https://www.aspensnowmass.com",
                weather_sources=["weatherapi"],
                created_at=now,
                updated_at=now,
            ),
            # ===== EUROPEAN RESORTS =====
            Resort(
                resort_id="chamonix",
                name="Chamonix Mont-Blanc",
                country="FR",
                region="Auvergne-Rhône-Alpes",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=1035,
                        elevation_feet=3396,
                        latitude=45.923697,
                        longitude=6.869433,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=2765,
                        elevation_feet=9071,
                        latitude=45.906697,
                        longitude=6.882433,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=3842,
                        elevation_feet=12605,
                        latitude=45.895697,
                        longitude=6.900433,
                        weather_station_id=None,
                    ),
                ],
                timezone="Europe/Paris",
                official_website="https://www.chamonix.com",
                weather_sources=["weatherapi"],
                created_at=now,
                updated_at=now,
            ),
            Resort(
                resort_id="zermatt",
                name="Zermatt Matterhorn",
                country="CH",
                region="Valais",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=1620,
                        elevation_feet=5315,
                        latitude=46.019831,
                        longitude=7.748512,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=2939,
                        elevation_feet=9642,
                        latitude=46.008831,
                        longitude=7.763512,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=3883,
                        elevation_feet=12740,
                        latitude=45.996831,
                        longitude=7.778512,
                        weather_station_id=None,
                    ),
                ],
                timezone="Europe/Zurich",
                official_website="https://www.zermatt.ch",
                weather_sources=["weatherapi"],
                created_at=now,
                updated_at=now,
            ),
            Resort(
                resort_id="st-anton",
                name="St. Anton am Arlberg",
                country="AT",
                region="Tyrol",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=1304,
                        elevation_feet=4278,
                        latitude=47.127778,
                        longitude=10.264167,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=2085,
                        elevation_feet=6841,
                        latitude=47.121778,
                        longitude=10.255167,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=2811,
                        elevation_feet=9222,
                        latitude=47.115778,
                        longitude=10.246167,
                        weather_station_id=None,
                    ),
                ],
                timezone="Europe/Vienna",
                official_website="https://www.stantonamarlberg.com",
                weather_sources=["weatherapi"],
                created_at=now,
                updated_at=now,
            ),
            Resort(
                resort_id="verbier",
                name="Verbier 4 Vallées",
                country="CH",
                region="Valais",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=1500,
                        elevation_feet=4921,
                        latitude=46.096531,
                        longitude=7.228917,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=2500,
                        elevation_feet=8202,
                        latitude=46.090531,
                        longitude=7.248917,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=3330,
                        elevation_feet=10925,
                        latitude=46.084531,
                        longitude=7.268917,
                        weather_station_id=None,
                    ),
                ],
                timezone="Europe/Zurich",
                official_website="https://www.verbier.ch",
                weather_sources=["weatherapi"],
                created_at=now,
                updated_at=now,
            ),
            # ===== JAPANESE RESORTS =====
            Resort(
                resort_id="niseko",
                name="Niseko United",
                country="JP",
                region="Hokkaido",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=260,
                        elevation_feet=853,
                        latitude=42.863333,
                        longitude=140.685833,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=800,
                        elevation_feet=2625,
                        latitude=42.858333,
                        longitude=140.695833,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=1308,
                        elevation_feet=4291,
                        latitude=42.853333,
                        longitude=140.705833,
                        weather_station_id=None,
                    ),
                ],
                timezone="Asia/Tokyo",
                official_website="https://www.niseko.ne.jp",
                weather_sources=["weatherapi"],
                created_at=now,
                updated_at=now,
            ),
            Resort(
                resort_id="hakuba",
                name="Hakuba Valley",
                country="JP",
                region="Nagano",
                elevation_points=[
                    ElevationPoint(
                        level=ElevationLevel.BASE,
                        elevation_meters=760,
                        elevation_feet=2493,
                        latitude=36.698056,
                        longitude=137.831944,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.MID,
                        elevation_meters=1400,
                        elevation_feet=4593,
                        latitude=36.691056,
                        longitude=137.840944,
                        weather_station_id=None,
                    ),
                    ElevationPoint(
                        level=ElevationLevel.TOP,
                        elevation_meters=1831,
                        elevation_feet=6007,
                        latitude=36.684056,
                        longitude=137.849944,
                        weather_station_id=None,
                    ),
                ],
                timezone="Asia/Tokyo",
                official_website="https://www.hakubavalley.com",
                weather_sources=["weatherapi"],
                created_at=now,
                updated_at=now,
            ),
        ]

    def get_resort_summary(self) -> dict[str, Any]:
        """Get a summary of current resorts in the database."""
        try:
            resorts = self.resort_service.get_all_resorts()

            summary = {
                "total_resorts": len(resorts),
                "resorts_by_country": {},
                "resorts_by_region": {},
                "elevation_ranges": {},
            }

            for resort in resorts:
                # Count by country
                country = resort.country
                if country in summary["resorts_by_country"]:
                    summary["resorts_by_country"][country] += 1
                else:
                    summary["resorts_by_country"][country] = 1

                # Count by region
                region = f"{resort.region}, {resort.country}"
                if region in summary["resorts_by_region"]:
                    summary["resorts_by_region"][region] += 1
                else:
                    summary["resorts_by_region"][region] = 1

                # Calculate elevation range
                elevations = [
                    point.elevation_meters for point in resort.elevation_points
                ]
                min_elevation = min(elevations)
                max_elevation = max(elevations)

                summary["elevation_ranges"][resort.resort_id] = {
                    "name": resort.name,
                    "min_elevation_m": min_elevation,
                    "max_elevation_m": max_elevation,
                    "vertical_drop_m": max_elevation - min_elevation,
                    "elevation_points": len(resort.elevation_points),
                }

            return summary

        except Exception as e:
            logger.error(f"Failed to generate resort summary: {str(e)}")
            raise

    def validate_resort_data(self) -> dict[str, Any]:
        """Validate the integrity of resort data in the database."""
        try:
            resorts = self.resort_service.get_all_resorts()
            validation_results = {
                "total_resorts": len(resorts),
                "valid_resorts": 0,
                "issues": [],
                "warnings": [],
            }

            for resort in resorts:
                issues = []

                # Check required fields
                if not resort.name or len(resort.name.strip()) < 2:
                    issues.append("Invalid or missing resort name")

                valid_countries = [
                    "CA",
                    "US",
                    "FR",
                    "CH",
                    "AT",
                    "JP",
                    "IT",
                    "DE",
                    "NO",
                    "SE",
                ]
                if resort.country not in valid_countries:
                    issues.append(f"Unexpected country code: {resort.country}")

                if not resort.timezone:
                    issues.append("Missing timezone information")

                # Validate elevation points
                if len(resort.elevation_points) < 2:
                    issues.append("Resort should have at least 2 elevation points")

                required_levels = {ElevationLevel.BASE, ElevationLevel.TOP}
                existing_levels = {point.level for point in resort.elevation_points}
                missing_levels = required_levels - existing_levels

                if missing_levels:
                    issues.append(
                        f"Missing required elevation levels: {[lvl.value for lvl in missing_levels]}"
                    )

                # Validate coordinates
                for point in resort.elevation_points:
                    if not (-90 <= point.latitude <= 90):
                        issues.append(
                            f"Invalid latitude for {point.level.value}: {point.latitude}"
                        )
                    if not (-180 <= point.longitude <= 180):
                        issues.append(
                            f"Invalid longitude for {point.level.value}: {point.longitude}"
                        )

                # Check elevation progression
                sorted_points = sorted(
                    resort.elevation_points, key=lambda p: p.elevation_meters
                )
                for i in range(1, len(sorted_points)):
                    if (
                        sorted_points[i].elevation_meters
                        <= sorted_points[i - 1].elevation_meters
                    ):
                        validation_results["warnings"].append(
                            f"{resort.name}: Elevation points may not be properly ordered"
                        )
                        break

                if issues:
                    validation_results["issues"].append(
                        {
                            "resort_id": resort.resort_id,
                            "resort_name": resort.name,
                            "issues": issues,
                        }
                    )
                else:
                    validation_results["valid_resorts"] += 1

            return validation_results

        except Exception as e:
            logger.error(f"Failed to validate resort data: {str(e)}")
            raise

    def export_resort_data(self, file_path: str = None) -> str:
        """Export current resort data to JSON file."""
        try:
            resorts = self.resort_service.get_all_resorts()

            export_data = {
                "export_timestamp": datetime.now(UTC).isoformat(),
                "total_resorts": len(resorts),
                "resorts": [resort.dict() for resort in resorts],
            }

            if not file_path:
                file_path = f"resort_data_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Successfully exported {len(resorts)} resorts to {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to export resort data: {str(e)}")
            raise
