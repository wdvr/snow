"""Lambda handler for scraping resorts from a specific country/region.

This worker Lambda is invoked by the scraper orchestrator to process
one country at a time, enabling parallel scraping across multiple Lambdas.
"""

import json
import logging
import os
import re
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import boto3
import requests
from bs4 import BeautifulSoup

from utils.geo_utils import encode_geohash

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
sns = boto3.client("sns")

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "snow-tracker-pulumi-state-us-west-2")
RESORTS_TABLE = os.environ.get("RESORTS_TABLE", "snow-tracker-resorts-dev")
NEW_RESORTS_TOPIC_ARN = os.environ.get("NEW_RESORTS_TOPIC_ARN", "")

# Scraper constants
USER_AGENT = (
    "Mozilla/5.0 (compatible; SnowTrackerBot/1.0; +https://github.com/snowtracker)"
)
REQUEST_DELAY = 1.0  # Seconds between requests
MAX_RETRIES = 3
MIN_VERTICAL = 300  # Minimum vertical drop in meters

# Country URL mappings for skiresort.info
COUNTRY_URLS = {
    "US": "/ski-resorts/usa",
    "CA": "/ski-resorts/canada",
    "AT": "/ski-resorts/austria",
    "CH": "/ski-resorts/switzerland",
    "FR": "/ski-resorts/france",
    "IT": "/ski-resorts/italy",
    "DE": "/ski-resorts/germany",
    "SI": "/ski-resorts/slovenia",
    "NO": "/ski-resorts/norway",
    "SE": "/ski-resorts/sweden",
    "FI": "/ski-resorts/finland",
    "JP": "/ski-resorts/japan",
    "AU": "/ski-resorts/australia",
    "NZ": "/ski-resorts/new-zealand",
    "CL": "/ski-resorts/chile",
    "AR": "/ski-resorts/argentina",
    "ES": "/ski-resorts/spain",
    "AD": "/ski-resorts/andorra",
    "PL": "/ski-resorts/poland",
    "CZ": "/ski-resorts/czech-republic",
    "SK": "/ski-resorts/slovakia",
    "KR": "/ski-resorts/south-korea",
    "CN": "/ski-resorts/china",
}

# Region mappings
REGION_MAPPINGS = {
    "FR": "alps",
    "CH": "alps",
    "AT": "alps",
    "IT": "alps",
    "DE": "alps",
    "SI": "alps",
    "AD": "alps",
    "ES": "alps",
    "NO": "scandinavia",
    "SE": "scandinavia",
    "FI": "scandinavia",
    "US": "na_rockies",
    "CA": "na_west",
    "JP": "japan",
    "AU": "oceania",
    "NZ": "oceania",
    "CL": "south_america",
    "AR": "south_america",
    "PL": "europe_east",
    "CZ": "europe_east",
    "SK": "europe_east",
    "KR": "asia",
    "CN": "asia",
}

# US state to region mapping
US_STATE_REGIONS = {
    "CA": "na_west",
    "OR": "na_west",
    "WA": "na_west",
    "CO": "na_rockies",
    "UT": "na_rockies",
    "WY": "na_rockies",
    "MT": "na_rockies",
    "ID": "na_rockies",
    "NM": "na_rockies",
    "AZ": "na_rockies",
    "NV": "na_rockies",
    "VT": "na_east",
    "NH": "na_east",
    "ME": "na_east",
    "NY": "na_east",
    "PA": "na_east",
    "MA": "na_east",
    "MI": "na_midwest",
    "WI": "na_midwest",
    "MN": "na_midwest",
}

# Canadian province to region mapping
CA_PROVINCE_REGIONS = {
    "BC": "na_west",
    "AB": "na_rockies",
    "ON": "na_east",
    "QC": "na_east",
}


class ScraperSession:
    """HTTP session with rate limiting and retries."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self._last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def get(self, url: str, **kwargs) -> requests.Response:
        """Make a rate-limited GET request with retries."""
        self._rate_limit()

        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(url, timeout=30, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2**attempt)
                else:
                    raise

        raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES} attempts")

    def get_soup(self, url: str, **kwargs) -> BeautifulSoup:
        """Fetch URL and return BeautifulSoup object."""
        response = self.get(url, **kwargs)
        return BeautifulSoup(response.text, "html.parser")


def get_region(country: str, state_province: str = "") -> str:
    """Determine the region based on country and state/province."""
    if country == "US" and state_province in US_STATE_REGIONS:
        return US_STATE_REGIONS[state_province]
    if country == "CA" and state_province in CA_PROVINCE_REGIONS:
        return CA_PROVINCE_REGIONS[state_province]
    return REGION_MAPPINGS.get(country, "other")


def collect_resort_urls(session: ScraperSession, country: str) -> list[tuple[str, str]]:
    """Collect all resort URLs from a country's listing pages."""
    base_url = "https://www.skiresort.info"
    url = urljoin(base_url, COUNTRY_URLS[country])
    resort_urls = []
    page = 1

    while True:
        page_url = f"{url}/page/{page}" if page > 1 else url

        try:
            soup = session.get_soup(page_url)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                break
            raise

        # Find resort links
        links = soup.select("a[href*='/ski-resort/']")
        seen = set()
        skip_patterns = [
            "/snow-report",
            "/test-report",
            "/reviews",
            "/photos",
            "/webcams",
            "/trail-map",
        ]

        for link in links:
            href = link.get("href", "")
            if any(pattern in href for pattern in skip_patterns):
                continue
            full_url = urljoin(base_url, href)
            if "/ski-resort/" in full_url and full_url not in seen:
                seen.add(full_url)
                resort_urls.append((full_url, country))

        # Check for next page
        next_link = soup.select_one(".pagination .next, a[rel='next']")
        if not next_link or page >= 20:
            break
        page += 1

    return resort_urls


def scrape_resort_detail(
    session: ScraperSession, url: str, country: str
) -> dict | None:
    """Scrape detailed resort information from its page."""
    try:
        soup = session.get_soup(url)
    except Exception as e:
        logger.warning(f"Failed to fetch resort detail {url}: {e}")
        return None

    # Extract name
    name_elem = soup.select_one("h1, .resort-name, .title")
    if not name_elem:
        return None
    name = name_elem.get_text(strip=True)

    # Clean name
    name = re.sub(r"^(?:Ski resort |Ski Resort )", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*[-–]\s*Ski Resort.*$", "", name, flags=re.IGNORECASE)

    # Skip non-resort pages
    skip_prefixes = ["Snow report", "Test report", "Trail map", "Events", "Webcams"]
    if any(name.lower().startswith(prefix.lower()) for prefix in skip_prefixes):
        return None

    # Extract elevation - target the elevation/altitude section specifically
    # to avoid matching random numbers (trail lengths, distances, etc.)
    elevation_base = None
    elevation_top = None

    # Try to find elevation in structured data sections first
    # skiresort.info uses specific sections for elevation data
    elevation_section = soup.find(
        string=re.compile(r"(?:altitude|elevation|höhe)", re.IGNORECASE)
    )
    search_text = ""
    if elevation_section:
        # Search in the parent and sibling elements near the elevation label
        parent = elevation_section.find_parent()
        if parent:
            # Look in the parent's parent for a broader section
            grandparent = parent.find_parent()
            search_text = (grandparent or parent).get_text()

    # Fallback: look for "base" and "top/summit" patterns in page text
    if not search_text:
        full_text = soup.get_text()
        # Match patterns like "1035 m - 3842 m" or "Base: 1035m ... Top: 3842m"
        range_match = re.search(r"(\d{3,4})\s*m\s*[-–]\s*(\d{3,4})\s*m", full_text)
        if range_match:
            elevation_base = int(range_match.group(1))
            elevation_top = int(range_match.group(2))
            if elevation_base > elevation_top:
                elevation_base, elevation_top = elevation_top, elevation_base
        else:
            search_text = full_text

    if search_text and not (elevation_base and elevation_top):
        all_elevations = re.findall(r"(\d{3,4})\s*m", search_text)
        all_elevations = [int(e) for e in all_elevations if 100 < int(e) < 5000]
        if len(all_elevations) >= 2:
            elevation_base = min(all_elevations)
            elevation_top = max(all_elevations)

    if not elevation_base or not elevation_top:
        return None

    # Check minimum vertical
    if (elevation_top - elevation_base) < MIN_VERTICAL:
        return None

    # Extract state/province
    state_province = extract_state_province(soup, country)

    # Extract coordinates from page, fallback to geocoding API
    latitude, longitude = extract_coordinates(soup)
    if latitude == 0.0 and longitude == 0.0:
        # Try geocoding as fallback
        latitude, longitude = geocode_resort(name, country)

    # Generate resort ID
    resort_id = generate_resort_id(name)

    # Compute geohash for geospatial indexing (precision 4 = ~39km cells)
    geo_hash = None
    if latitude and longitude and latitude != 0.0 and longitude != 0.0:
        geo_hash = encode_geohash(latitude, longitude, precision=4)

    return {
        "resort_id": resort_id,
        "name": name,
        "country": country,
        "region": get_region(country, state_province),
        "state_province": state_province,
        "elevation_base_m": elevation_base,
        "elevation_top_m": elevation_top,
        "latitude": latitude,
        "longitude": longitude,
        "geo_hash": geo_hash,
        "source": "skiresort.info",
        "source_url": url,
        "scraped_at": datetime.now(UTC).isoformat(),
    }


def extract_state_province(soup: BeautifulSoup, country: str) -> str:
    """Extract state/province from the page."""
    mobile_header = soup.select_one(".mobile-header-regionselector")
    if mobile_header:
        text = mobile_header.get_text()

        if country == "US":
            match = re.search(
                r"USA([A-Z][a-z]+(?:\s[A-Z][a-z]+)*?)(?=[A-Z][a-z]|$)", text
            )
            if match:
                state = match.group(1).strip()
                if state not in ["Worldwide", "North", "Search"]:
                    return state

        if country == "CA":
            match = re.search(
                r"Canada([A-Z][a-z]+(?:\s[A-Z][a-z]+)*?)(?=[A-Z][a-z]|$)", text
            )
            if match:
                province = match.group(1).strip()
                if province not in ["Worldwide", "North", "Search"]:
                    return province

    return ""


def extract_coordinates(soup: BeautifulSoup) -> tuple[float, float]:
    """Extract coordinates from the page."""
    # Try data attributes
    map_elem = soup.select_one("[data-lat], [data-latitude]")
    if map_elem:
        lat = map_elem.get("data-lat") or map_elem.get("data-latitude")
        lon = (
            map_elem.get("data-lng")
            or map_elem.get("data-lon")
            or map_elem.get("data-longitude")
        )
        if lat and lon:
            return float(lat), float(lon)

    # Try scripts
    for script in soup.find_all("script"):
        if script.string:
            lat_match = re.search(r"lat[itude]*[\"':\s]+(-?\d+\.?\d*)", script.string)
            lng_match = re.search(
                r"(?:lng|lon)[gitude]*[\"':\s]+(-?\d+\.?\d*)", script.string
            )
            if lat_match and lng_match:
                return float(lat_match.group(1)), float(lng_match.group(1))

    return 0.0, 0.0


def geocode_resort(name: str, country: str) -> tuple[float, float]:
    """
    Geocode a resort using Open-Meteo's free geocoding API.
    Returns (0.0, 0.0) if geocoding fails.
    """
    try:
        # Clean name for search
        clean_name = name.lower()
        clean_name = re.sub(r"ski resort|ski area|mountain resort", "", clean_name)
        clean_name = re.sub(r"[–-]", " ", clean_name)
        clean_name = re.sub(r"\s+", " ", clean_name).strip()

        # Try Open-Meteo geocoding API (free, no API key needed)
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {
            "name": f"{clean_name} ski",
            "count": 5,
            "language": "en",
            "format": "json",
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        if not results:
            # Try without "ski" suffix
            params["name"] = clean_name
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])

        if results:
            # Find best match (prefer results in the right country)
            for result in results:
                if result.get("country_code", "").upper() == country.upper():
                    lat = result.get("latitude", 0.0)
                    lon = result.get("longitude", 0.0)
                    if lat != 0.0 or lon != 0.0:
                        logger.info(f"Geocoded {name} ({country}) -> {lat}, {lon}")
                        return lat, lon

            # Fallback to first result if country doesn't match
            lat = results[0].get("latitude", 0.0)
            lon = results[0].get("longitude", 0.0)
            if lat != 0.0 or lon != 0.0:
                logger.info(f"Geocoded {name} (fallback) -> {lat}, {lon}")
                return lat, lon

    except Exception as e:
        logger.warning(f"Geocoding failed for {name}: {e}")

    return 0.0, 0.0


def generate_resort_id(name: str) -> str:
    """Generate a URL-friendly resort ID from the name."""
    resort_id = name.lower()
    resort_id = re.sub(r"[''`]", "", resort_id)
    resort_id = re.sub(r"[àáâãäå]", "a", resort_id)
    resort_id = re.sub(r"[èéêë]", "e", resort_id)
    resort_id = re.sub(r"[ìíîï]", "i", resort_id)
    resort_id = re.sub(r"[òóôõö]", "o", resort_id)
    resort_id = re.sub(r"[ùúûü]", "u", resort_id)
    resort_id = re.sub(r"[^a-z0-9]+", "-", resort_id)
    resort_id = resort_id.strip("-")
    resort_id = re.sub(r"-+", "-", resort_id)
    return resort_id


def get_existing_resort_ids() -> set[str]:
    """Get set of existing resort IDs from DynamoDB."""
    table = dynamodb.Table(RESORTS_TABLE)
    existing_ids = set()

    try:
        response = table.scan(ProjectionExpression="resort_id")
        existing_ids.update(item["resort_id"] for item in response.get("Items", []))

        while "LastEvaluatedKey" in response:
            response = table.scan(
                ProjectionExpression="resort_id",
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            existing_ids.update(item["resort_id"] for item in response.get("Items", []))

    except Exception as e:
        logger.warning(f"Failed to fetch existing resort IDs: {e}")

    return existing_ids


def publish_new_resorts_notification(
    new_resorts: list[dict[str, Any]], country: str, job_id: str
) -> None:
    """Publish SNS notification for newly discovered resorts."""
    if not NEW_RESORTS_TOPIC_ARN or not new_resorts:
        return

    try:
        # Count resorts without coordinates
        no_coords = [
            r
            for r in new_resorts
            if r.get("latitude", 0) == 0.0 and r.get("longitude", 0) == 0.0
        ]
        has_coords = len(new_resorts) - len(no_coords)

        # Create summary message
        subject = (
            f"[{ENVIRONMENT}] {len(new_resorts)} new resorts discovered in {country}"
        )
        if no_coords:
            subject += f" ({len(no_coords)} missing coords)"

        message_lines = [
            f"Scraper Job ID: {job_id}",
            f"Country: {country}",
            f"New Resorts Found: {len(new_resorts)}",
            f"With Coordinates: {has_coords}",
            f"Missing Coordinates: {len(no_coords)}",
            "",
            "Resorts:",
        ]

        for resort in new_resorts[:20]:
            name = resort.get("name", "Unknown")
            region = resort.get("region", "Unknown")
            vertical = resort.get("elevation_top_m", 0) - resort.get(
                "elevation_base_m", 0
            )
            coords_status = (
                ""
                if (
                    resort.get("latitude", 0) != 0.0
                    or resort.get("longitude", 0) != 0.0
                )
                else " [NO COORDS]"
            )
            message_lines.append(
                f"  - {name} ({region}) - {vertical}m vertical{coords_status}"
            )

        if len(new_resorts) > 20:
            message_lines.append(f"  ... and {len(new_resorts) - 20} more")

        # Add warning about missing coordinates
        if no_coords:
            message_lines.extend(
                [
                    "",
                    "⚠️ WARNING: Resorts without coordinates will not appear on the map.",
                    "Please manually geocode these resorts or verify the scraper extraction.",
                    "",
                    "Resorts missing coordinates:",
                ]
            )
            for resort in no_coords[:10]:
                message_lines.append(f"  - {resort.get('name', 'Unknown')}")
            if len(no_coords) > 10:
                message_lines.append(f"  ... and {len(no_coords) - 10} more")

        message_lines.extend(
            [
                "",
                f"Results stored in: s3://{RESULTS_BUCKET}/scraper-results/{job_id}/{country}.json",
            ]
        )

        message = "\n".join(message_lines)

        sns.publish(
            TopicArn=NEW_RESORTS_TOPIC_ARN,
            Subject=subject[:100],  # SNS subject limit
            Message=message,
        )
        logger.info(
            f"Published SNS notification for {len(new_resorts)} new resorts ({len(no_coords)} without coords)"
        )

    except Exception as e:
        logger.error(f"Failed to publish new resorts notification: {e}")


def scraper_worker_handler(event: dict[str, Any], context) -> dict[str, Any]:
    """
    Lambda handler for scraping resorts from a specific country.

    Args:
        event: Contains:
            - country: Country code to scrape (e.g., "US", "CA", "FR")
            - delta_mode: If true, skip existing resorts (default: true)
            - job_id: Unique job ID for storing results
        context: Lambda context object

    Returns:
        Dict with scraping results
    """
    country = event.get("country")
    delta_mode = event.get("delta_mode", True)
    job_id = event.get("job_id", datetime.now(UTC).strftime("%Y%m%d%H%M%S"))

    if not country or country not in COUNTRY_URLS:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"Invalid country: {country}"}),
        }

    logger.info(f"Starting scrape for country {country}, delta_mode={delta_mode}")

    stats = {
        "country": country,
        "resorts_scraped": 0,
        "resorts_skipped": 0,
        "errors": 0,
        "start_time": datetime.now(UTC).isoformat(),
    }

    try:
        session = ScraperSession()

        # Get existing resort IDs for delta mode
        existing_ids = get_existing_resort_ids() if delta_mode else set()
        if existing_ids:
            logger.info(
                f"Delta mode: {len(existing_ids)} existing resorts will be skipped"
            )

        # Collect resort URLs
        logger.info(f"Collecting resort URLs for {country}...")
        resort_urls = collect_resort_urls(session, country)
        logger.info(f"Found {len(resort_urls)} resort URLs")

        # Scrape each resort
        scraped_resorts = []
        for url, country_code in resort_urls:
            try:
                # Check if already exists in delta mode
                url_id = url.split("/ski-resort/")[-1].rstrip("/")
                if delta_mode and url_id in existing_ids:
                    stats["resorts_skipped"] += 1
                    continue

                resort = scrape_resort_detail(session, url, country_code)
                if resort:
                    # Double-check ID doesn't exist
                    if delta_mode and resort["resort_id"] in existing_ids:
                        stats["resorts_skipped"] += 1
                        continue

                    scraped_resorts.append(resort)
                    stats["resorts_scraped"] += 1
                    logger.info(f"Scraped: {resort['name']}")

            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                stats["errors"] += 1

        stats["end_time"] = datetime.now(UTC).isoformat()
        stats["duration_seconds"] = (
            datetime.fromisoformat(stats["end_time"].replace("Z", "+00:00"))
            - datetime.fromisoformat(stats["start_time"].replace("Z", "+00:00"))
        ).total_seconds()

        # Store results in S3
        if scraped_resorts:
            results_key = f"scraper-results/{job_id}/{country}.json"
            s3.put_object(
                Bucket=RESULTS_BUCKET,
                Key=results_key,
                Body=json.dumps({"resorts": scraped_resorts, "stats": stats}),
                ContentType="application/json",
            )
            logger.info(
                f"Stored {len(scraped_resorts)} resorts to s3://{RESULTS_BUCKET}/{results_key}"
            )

            # Send SNS notification for new resorts
            publish_new_resorts_notification(scraped_resorts, country, job_id)

        logger.info(
            f"Scrape complete for {country}: "
            f"{stats['resorts_scraped']} scraped, "
            f"{stats['resorts_skipped']} skipped, "
            f"{stats['errors']} errors"
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": f"Scraped {stats['resorts_scraped']} resorts from {country}",
                    "country": country,
                    "resorts_scraped": stats["resorts_scraped"],
                    "resorts_skipped": stats["resorts_skipped"],
                    "errors": stats["errors"],
                    "duration_seconds": stats["duration_seconds"],
                }
            ),
        }

    except Exception as e:
        logger.error(f"Fatal error scraping {country}: {str(e)}")
        stats["errors"] += 1

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "message": f"Scraper failed for {country}",
                    "error": str(e),
                    "stats": stats,
                }
            ),
        }
