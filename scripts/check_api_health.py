#!/usr/bin/env python3
"""
API Health Check Script - Verifies API endpoints and response formats.
Run this to check if the iOS app will work correctly with the API.

Usage: python3 scripts/check_api_health.py
"""

import json
import sys
import urllib.request
import urllib.error
from typing import Any

STAGING_URL = "https://mhserjdtp1.execute-api.us-west-2.amazonaws.com/staging"
PROD_URL = "https://z1f5zrp4l0.execute-api.us-west-2.amazonaws.com/prod"


def fetch_json(url: str, timeout: int = 10) -> dict[str, Any]:
    """Fetch JSON from URL."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "SnowTracker-HealthCheck/1.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def check_endpoint(
    base_url: str, endpoint: str, expected_keys: list[str]
) -> tuple[bool, str]:
    """Check an endpoint returns expected JSON structure."""
    url = f"{base_url}{endpoint}"
    try:
        data = fetch_json(url)
        missing_keys = [k for k in expected_keys if k not in data]
        if missing_keys:
            return False, f"Missing keys: {missing_keys}"
        return True, f"OK ({len(str(data))} bytes)"
    except urllib.error.URLError as e:
        return False, f"Request failed: {e}"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"


def check_resorts_format(base_url: str) -> tuple[bool, str]:
    """Check resorts endpoint returns wrapped format."""
    url = f"{base_url}/api/v1/resorts"
    try:
        data = fetch_json(url)

        if isinstance(data, list):
            return False, "ERROR: Returns raw array, iOS expects {resorts: [...]}"
        if "resorts" not in data:
            return False, f"ERROR: Missing 'resorts' key, got: {list(data.keys())}"
        if not isinstance(data["resorts"], list):
            return False, "ERROR: 'resorts' is not an array"

        return True, f"OK - {len(data['resorts'])} resorts"
    except Exception as e:
        return False, f"FAILED: {e}"


def check_conditions_format(
    base_url: str, resort_id: str = "big-white"
) -> tuple[bool, str]:
    """Check conditions endpoint returns correct format with decodable rawData."""
    url = f"{base_url}/api/v1/resorts/{resort_id}/conditions"
    try:
        data = fetch_json(url)

        if "conditions" not in data:
            return False, "ERROR: Missing 'conditions' key"

        conditions = data["conditions"]
        if not conditions:
            return True, "OK - 0 conditions (empty)"

        # Check first condition has expected fields
        required_fields = [
            "resort_id",
            "elevation_level",
            "timestamp",
            "current_temp_celsius",
            "snow_quality",
            "confidence_level",
        ]
        first = conditions[0]
        missing = [f for f in required_fields if f not in first]
        if missing:
            return False, f"ERROR: Condition missing fields: {missing}"

        # Check raw_data is present (can be complex JSON)
        if "raw_data" in first and first["raw_data"] is not None:
            raw = first["raw_data"]
            if not isinstance(raw, dict):
                return False, "ERROR: raw_data is not a dict"

        return (
            True,
            f"OK - {len(conditions)} conditions, quality: {first['snow_quality']}",
        )
    except Exception as e:
        return False, f"FAILED: {e}"


def main():
    print("=" * 60)
    print("Snow Tracker API Health Check")
    print("=" * 60)

    all_passed = True

    for env_name, base_url in [("STAGING", STAGING_URL), ("PROD", PROD_URL)]:
        print(f"\n{env_name}: {base_url}")
        print("-" * 40)

        # Health check
        ok, msg = check_endpoint(base_url, "/health", ["status"])
        status = "✓" if ok else "✗"
        print(f"  {status} Health: {msg}")
        all_passed = all_passed and ok

        # Resorts format
        ok, msg = check_resorts_format(base_url)
        status = "✓" if ok else "✗"
        print(f"  {status} Resorts: {msg}")
        all_passed = all_passed and ok

        # Conditions format
        ok, msg = check_conditions_format(base_url)
        status = "✓" if ok else "✗"
        print(f"  {status} Conditions: {msg}")
        all_passed = all_passed and ok

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All checks passed - iOS app should work correctly")
        return 0
    else:
        print("✗ Some checks failed - iOS app may have issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())
