"""Service for generating natural language explanations of snow quality scores."""

from models.weather import SnowQuality, WeatherCondition


def generate_quality_explanation(condition: WeatherCondition) -> str:
    """Generate a human-readable explanation for a snow quality assessment.

    Takes a WeatherCondition and returns a natural language string explaining
    why the quality is rated as it is, what the key factors are, and what
    to expect in the near future.
    """
    parts = []

    quality = condition.snow_quality
    if isinstance(quality, str):
        quality = SnowQuality(quality)

    # 1. Surface condition description
    surface = _describe_surface(condition)
    if surface:
        parts.append(surface)

    # 2. Fresh snow context
    fresh = _describe_fresh_snow(condition)
    if fresh:
        parts.append(fresh)

    # 3. Temperature context
    temp = _describe_temperature(condition)
    if temp:
        parts.append(temp)

    # 4. Base depth context
    base = _describe_base(condition)
    if base:
        parts.append(base)

    # 5. Forecast outlook
    forecast = _describe_forecast(condition)
    if forecast:
        parts.append(forecast)

    return " ".join(parts) if parts else _default_explanation(quality)


def _describe_surface(condition: WeatherCondition) -> str:
    """Describe the likely surface condition based on data."""
    quality = condition.snow_quality
    if isinstance(quality, str):
        quality = SnowQuality(quality)

    fresh_cm = condition.fresh_snow_cm or 0
    snow_24h = condition.snowfall_24h_cm or 0
    snow_48h = condition.snowfall_48h_cm or 0
    hours_since = condition.hours_since_last_snowfall
    freeze_thaw_ago = condition.last_freeze_thaw_hours_ago
    temp = condition.current_temp_celsius
    warming = condition.currently_warming

    if quality == SnowQuality.EXCELLENT:
        if snow_24h >= 10:
            return f"Fresh powder: {snow_24h:.0f}cm in the last 24 hours."
        elif snow_48h >= 10:
            return f"Fresh powder: {snow_48h:.0f}cm in the last 48 hours."
        elif fresh_cm >= 7.6:
            return f"Fresh powder: {fresh_cm:.0f}cm of uncompacted snow."
        return "Fresh powder conditions."

    if quality == SnowQuality.GOOD:
        if snow_24h >= 5:
            return f"Soft surface with {snow_24h:.0f}cm of recent snow."
        elif fresh_cm >= 5:
            if hours_since and hours_since > 48:
                return f"Settled powder: {fresh_cm:.0f}cm of snow, last snowfall {_format_hours(hours_since)} ago."
            return f"Good coverage with {fresh_cm:.0f}cm of non-refrozen snow."
        return "Soft, rideable surface."

    if quality == SnowQuality.FAIR:
        if hours_since and hours_since > 72 and fresh_cm > 5:
            return f"Packed powder: {fresh_cm:.0f}cm of aged snow (last snowfall {_format_hours(hours_since)} ago)."
        elif fresh_cm >= 2.5:
            if warming:
                return f"Some fresh snow ({fresh_cm:.0f}cm) but currently warming — surface softening."
            return f"Some fresh snow ({fresh_cm:.0f}cm) on a firm base."
        return "Firm, groomed-type surface with limited fresh snow."

    if quality == SnowQuality.POOR:
        if freeze_thaw_ago and freeze_thaw_ago < 72:
            return f"Thin cover over refrozen base. Last thaw-freeze {_format_hours(freeze_thaw_ago)} ago."
        return f"Hard packed surface with {fresh_cm:.0f}cm of aged snow."

    if quality == SnowQuality.BAD:
        if freeze_thaw_ago and freeze_thaw_ago < 48:
            return f"Icy: recent thaw-freeze cycle {_format_hours(freeze_thaw_ago)} ago with minimal fresh snow."
        return "Icy, refrozen surface. No significant fresh snow."

    if quality == SnowQuality.HORRIBLE:
        if temp > 5:
            return (
                f"Not skiable: warm temperatures ({temp:.0f}°C) actively melting snow."
            )
        return "Not skiable: insufficient snow cover."

    return ""


def _describe_fresh_snow(condition: WeatherCondition) -> str:
    """Describe fresh snow amounts and timing."""
    snow_24h = condition.snowfall_24h_cm or 0
    snow_48h = condition.snowfall_48h_cm or 0
    snow_72h = condition.snowfall_72h_cm or 0
    hours_since = condition.hours_since_last_snowfall

    # Skip if already covered in surface description
    if snow_24h >= 5 or snow_48h >= 10:
        return ""

    if snow_72h > 0 and snow_24h == 0:
        if hours_since and hours_since > 48:
            return f"No new snow in {_format_hours(hours_since)}."
        elif snow_72h >= 5:
            return f"{snow_72h:.0f}cm fell in the last 72 hours but none recently."

    return ""


def _describe_temperature(condition: WeatherCondition) -> str:
    """Describe temperature impact on conditions."""
    temp = condition.current_temp_celsius
    max_temp = condition.max_temp_celsius
    warming = condition.currently_warming
    warm_hours = condition.max_consecutive_warm_hours or 0

    if warming and temp > 0:
        return f"Currently {temp:.0f}°C — surface is softening."
    elif warming and temp > -2:
        return f"Near freezing ({temp:.0f}°C) — conditions may degrade."
    elif temp < -15:
        return f"Very cold ({temp:.0f}°C) — snow is firm and squeaky."
    elif temp < -8:
        return f"Cold ({temp:.0f}°C) — good preservation."
    elif temp < 0:
        return f"Cool ({temp:.0f}°C)."

    if temp > 3 and warm_hours > 2:
        return f"Warm ({temp:.0f}°C for {warm_hours:.0f}h) — expect soft, wet snow."

    return ""


def _describe_base(condition: WeatherCondition) -> str:
    """Describe base depth context."""
    depth = condition.snow_depth_cm
    if depth is None:
        return ""

    if depth >= 200:
        return f"Deep {depth:.0f}cm base."
    elif depth >= 100:
        return f"Solid {depth:.0f}cm base."
    elif depth >= 50:
        return f"{depth:.0f}cm base."
    elif depth > 0:
        return f"Thin {depth:.0f}cm base — limited terrain."

    return ""


def _describe_forecast(condition: WeatherCondition) -> str:
    """Describe the near-term forecast outlook."""
    pred_24 = condition.predicted_snow_24h_cm or 0
    pred_48 = condition.predicted_snow_48h_cm or 0
    pred_72 = condition.predicted_snow_72h_cm or 0

    if pred_24 >= 10:
        return f"Outlook: {pred_24:.0f}cm expected in the next 24 hours."
    elif pred_48 >= 10:
        return f"Outlook: {pred_48:.0f}cm expected in 48 hours."
    elif pred_72 >= 10:
        return f"Outlook: {pred_72:.0f}cm expected in the next 3 days."
    elif pred_72 >= 2:
        return f"Outlook: light snow ({pred_72:.0f}cm) in the next 3 days."
    elif pred_72 == 0:
        return "Outlook: no snow in the forecast."

    return ""


def _default_explanation(quality: SnowQuality) -> str:
    """Fallback explanation when data is insufficient."""
    defaults = {
        SnowQuality.EXCELLENT: "Excellent conditions with fresh powder.",
        SnowQuality.GOOD: "Good conditions with soft snow.",
        SnowQuality.FAIR: "Fair conditions. Groomed runs recommended.",
        SnowQuality.POOR: "Poor conditions. Thin or aged snow cover.",
        SnowQuality.BAD: "Icy conditions. Sharp edges recommended.",
        SnowQuality.HORRIBLE: "Not skiable. Insufficient snow cover.",
        SnowQuality.UNKNOWN: "Conditions data unavailable.",
    }
    return defaults.get(quality, "Conditions data unavailable.")


def _format_hours(hours: float) -> str:
    """Format hours into a human-readable time string."""
    if hours < 1:
        return "less than an hour"
    elif hours < 24:
        return f"{hours:.0f} hours"
    else:
        days = hours / 24
        if days < 1.5:
            return "1 day"
        return f"{days:.0f} days"


def generate_timeline_explanation(
    quality: str,
    temperature_c: float,
    snowfall_cm: float,
    snow_depth_cm: float | None,
    wind_speed_kmh: float | None,
    is_forecast: bool,
) -> str:
    """Generate a concise explanation for a timeline point.

    Uses the limited data available from timeline points (no freeze-thaw history,
    no rolling snowfall windows) to produce a 1-2 sentence explanation.
    """
    try:
        q = SnowQuality(quality) if isinstance(quality, str) else quality
    except ValueError:
        return "Conditions data unavailable."

    parts = []
    prefix = "Expected: " if is_forecast else ""

    # Surface/quality description
    if q == SnowQuality.EXCELLENT:
        if snowfall_cm >= 5:
            parts.append(f"{prefix}Fresh powder with {snowfall_cm:.0f}cm of snowfall.")
        else:
            parts.append(f"{prefix}Excellent powder conditions.")
    elif q == SnowQuality.GOOD:
        if snowfall_cm >= 2:
            parts.append(
                f"{prefix}Soft surface with {snowfall_cm:.0f}cm of recent snow."
            )
        else:
            parts.append(f"{prefix}Good, soft rideable surface.")
    elif q == SnowQuality.FAIR:
        if snowfall_cm >= 1:
            parts.append(
                f"{prefix}Some fresh snow ({snowfall_cm:.0f}cm) on a firm base."
            )
        else:
            parts.append(f"{prefix}Firm, groomed-type surface.")
    elif q == SnowQuality.POOR:
        parts.append(f"{prefix}Hard packed with limited fresh snow.")
    elif q == SnowQuality.BAD:
        parts.append(f"{prefix}Icy, refrozen surface.")
    elif q == SnowQuality.HORRIBLE:
        parts.append(f"{prefix}Not skiable.")
    else:
        return "Conditions data unavailable."

    # Temperature context (brief)
    if temperature_c > 3:
        parts.append(f"Warm ({temperature_c:.0f}°C) — wet snow.")
    elif temperature_c < -15:
        parts.append(f"Very cold ({temperature_c:.0f}°C).")
    elif temperature_c > 0:
        parts.append(f"Near freezing ({temperature_c:.0f}°C).")

    # Wind context
    if wind_speed_kmh and wind_speed_kmh > 40:
        parts.append(f"Strong wind ({wind_speed_kmh:.0f} km/h).")

    return " ".join(parts)


def score_to_100(raw_score: float) -> int:
    """Convert ML model raw score (1.0-6.0) to a 0-100 scale.

    1.0 (horrible) -> 0
    6.0 (excellent) -> 100
    """
    return max(0, min(100, round((raw_score - 1.0) / 5.0 * 100)))
