"""Load resort data from JSON file."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from models.resort import ElevationLevel, ElevationPoint, Resort

logger = logging.getLogger(__name__)

# Path to resort data JSON
DATA_FILE = Path(__file__).parent.parent.parent / "data" / "resorts.json"


class ResortLoader:
    """Load and transform resort data from JSON file."""

    def __init__(self, data_file: Path = DATA_FILE):
        self.data_file = data_file
        self._data: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        """Load data from JSON file."""
        if self._data is None:
            if not self.data_file.exists():
                raise FileNotFoundError(f"Resort data file not found: {self.data_file}")

            with open(self.data_file, "r", encoding="utf-8") as f:
                self._data = json.load(f)

            logger.info(f"Loaded {len(self._data.get('resorts', []))} resorts from {self.data_file}")

        return self._data

    def get_regions(self) -> dict[str, dict[str, Any]]:
        """Get all region definitions."""
        data = self.load()
        return data.get("regions", {})

    def get_region_list(self) -> list[dict[str, Any]]:
        """Get list of regions with counts."""
        data = self.load()
        regions = data.get("regions", {})
        resorts = data.get("resorts", [])

        # Count resorts per region
        region_counts = {}
        for resort in resorts:
            region = resort.get("region", "unknown")
            region_counts[region] = region_counts.get(region, 0) + 1

        result = []
        for region_id, region_info in regions.items():
            result.append({
                "id": region_id,
                "name": region_info.get("name", region_id),
                "display_name": region_info.get("display_name", region_id),
                "countries": region_info.get("countries", []),
                "resort_count": region_counts.get(region_id, 0),
            })

        return sorted(result, key=lambda r: -r["resort_count"])

    def get_resorts(self, region: str | None = None) -> list[Resort]:
        """
        Get all resorts as Resort model objects.

        Args:
            region: Optional region filter (e.g., 'na_west', 'alps')

        Returns:
            List of Resort objects ready for database insertion
        """
        data = self.load()
        raw_resorts = data.get("resorts", [])

        if region:
            raw_resorts = [r for r in raw_resorts if r.get("region") == region]

        now = datetime.now(UTC).isoformat()
        resorts = []

        for raw in raw_resorts:
            try:
                resort = self._transform_resort(raw, now)
                resorts.append(resort)
            except Exception as e:
                logger.warning(f"Failed to transform resort {raw.get('resort_id', 'unknown')}: {e}")

        return resorts

    def _transform_resort(self, raw: dict[str, Any], now: str) -> Resort:
        """Transform raw JSON resort data to Resort model."""
        base_elev_m = raw.get("elevation_base_m", 0)
        top_elev_m = raw.get("elevation_top_m", 0)
        mid_elev_m = (base_elev_m + top_elev_m) // 2

        lat = raw.get("latitude", 0.0)
        lon = raw.get("longitude", 0.0)

        # Estimate mid and top coordinates based on typical mountain layout
        lat_diff = 0.005 if lat > 0 else -0.005  # Slight northward movement for northern hemisphere
        lon_diff = 0.005

        elevation_points = [
            ElevationPoint(
                level=ElevationLevel.BASE,
                elevation_meters=base_elev_m,
                elevation_feet=int(base_elev_m * 3.28084),
                latitude=lat,
                longitude=lon,
                weather_station_id=None,
            ),
            ElevationPoint(
                level=ElevationLevel.MID,
                elevation_meters=mid_elev_m,
                elevation_feet=int(mid_elev_m * 3.28084),
                latitude=lat + lat_diff,
                longitude=lon + lon_diff,
                weather_station_id=None,
            ),
            ElevationPoint(
                level=ElevationLevel.TOP,
                elevation_meters=top_elev_m,
                elevation_feet=int(top_elev_m * 3.28084),
                latitude=lat + lat_diff * 2,
                longitude=lon + lon_diff * 2,
                weather_station_id=None,
            ),
        ]

        return Resort(
            resort_id=raw["resort_id"],
            name=raw["name"],
            country=raw["country"],
            region=raw.get("state_province", raw.get("region", "")),
            elevation_points=elevation_points,
            timezone=raw.get("timezone", "UTC"),
            official_website=raw.get("website"),
            weather_sources=["weatherapi"],
            created_at=now,
            updated_at=now,
        )

    def get_resort_by_id(self, resort_id: str) -> Resort | None:
        """Get a single resort by ID."""
        data = self.load()
        raw_resorts = data.get("resorts", [])

        for raw in raw_resorts:
            if raw.get("resort_id") == resort_id:
                now = datetime.now(UTC).isoformat()
                return self._transform_resort(raw, now)

        return None

    def get_resorts_by_country(self, country_code: str) -> list[Resort]:
        """Get all resorts in a specific country."""
        data = self.load()
        raw_resorts = [r for r in data.get("resorts", []) if r.get("country") == country_code]

        now = datetime.now(UTC).isoformat()
        return [self._transform_resort(raw, now) for raw in raw_resorts]


# Convenience function
def load_resorts(region: str | None = None) -> list[Resort]:
    """Load resorts from JSON file."""
    loader = ResortLoader()
    return loader.get_resorts(region)
