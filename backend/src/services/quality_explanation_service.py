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


def _describe_surface(
    condition: WeatherCondition,
    quality_override: SnowQuality | None = None,
) -> str:
    """Describe the likely surface condition based on data.

    Args:
        condition: Weather condition with snow data
        quality_override: If provided, use this quality level instead of
            the condition's own quality. Used when the overall quality
            differs from the representative elevation's quality.
    """
    quality = quality_override or condition.snow_quality
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
        # Use temperature-aware descriptions: below -5°C snow is dry, not soft
        is_cold = temp is not None and temp < -5
        if snow_24h >= 5:
            if is_cold:
                return f"Dry packed powder with {snow_24h:.0f}cm of recent snow."
            return f"Soft surface with {snow_24h:.0f}cm of recent snow."
        elif fresh_cm >= 80:
            return f"Deep base with {fresh_cm:.0f}cm of fresh snow."
        elif fresh_cm >= 5:
            if hours_since and hours_since > 48:
                return f"Settled powder: {fresh_cm:.0f}cm of snow, last snowfall {_format_hours(hours_since)} ago."
            return f"Good coverage with {fresh_cm:.0f}cm of fresh snow."
        if is_cold:
            return "Dry packed powder — good rideable surface."
        return "Soft, rideable surface."

    if quality == SnowQuality.FAIR:
        if fresh_cm >= 80:
            return f"Substantial base with {fresh_cm:.0f}cm of fresh snow."
        elif hours_since and hours_since > 72 and fresh_cm > 5:
            return f"Packed powder: {fresh_cm:.0f}cm of aged snow (last snowfall {_format_hours(hours_since)} ago)."
        elif fresh_cm >= 30:
            if warming:
                return f"Good base ({fresh_cm:.0f}cm fresh) but currently warming."
            return f"Good base with {fresh_cm:.0f}cm of fresh snow."
        elif fresh_cm >= 2.5:
            if warming:
                return f"Some fresh snow ({fresh_cm:.0f}cm) but currently warming — surface softening."
            return f"Some fresh snow ({fresh_cm:.0f}cm) on a firm base."
        return "Firm, groomed-type surface with limited fresh snow."

    if quality == SnowQuality.POOR:
        if freeze_thaw_ago and freeze_thaw_ago < 72:
            return f"Thin cover over refrozen base. Last thaw-freeze {_format_hours(freeze_thaw_ago)} ago."
        if fresh_cm >= 2.5:
            return f"Hard packed surface with {fresh_cm:.0f}cm of aged snow."
        return "Hard packed surface. No significant fresh snow."

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
        SnowQuality.GOOD: "Good rideable conditions.",
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
        # Use temperature-aware descriptions: below -5°C snow is dry, not soft
        is_cold = temperature_c < -5
        if snowfall_cm >= 2:
            if is_cold:
                parts.append(
                    f"{prefix}Dry packed powder with {snowfall_cm:.0f}cm of recent snow."
                )
            else:
                parts.append(
                    f"{prefix}Soft surface with {snowfall_cm:.0f}cm of recent snow."
                )
        else:
            if is_cold:
                parts.append(f"{prefix}Good, dry packed powder.")
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


def generate_overall_explanation(
    conditions: list[WeatherCondition],
    overall_quality: SnowQuality,
    representative: WeatherCondition | None = None,
) -> str | None:
    """Generate an overall explanation that accounts for all elevations.

    Uses the representative condition (mid > top > base) for all weather
    data (temperature, base depth, forecast) to ensure consistency with
    the temperature_c field in the API response.

    Args:
        conditions: All elevation conditions for the resort
        overall_quality: Weighted overall quality level
        representative: The condition used for temperature_c/snowfall fields.
            If not provided, will find one using mid > top > base preference.
    """
    if not conditions:
        return None

    if isinstance(overall_quality, str):
        overall_quality = SnowQuality(overall_quality)

    # Find representative if not provided (same order as temperature_c selection)
    if representative is None:
        for pref in ["mid", "top", "base"]:
            for c in conditions:
                if c.elevation_level == pref:
                    representative = c
                    break
            if representative:
                break
        if not representative:
            representative = conditions[0]

    # If representative's quality matches overall, use it directly
    if _norm_quality(representative.snow_quality) == overall_quality:
        return generate_quality_explanation(representative)

    # Quality differs — generate explanation using representative's weather data
    # with the overall quality level for surface description.
    # This ensures the temperature in the explanation matches temperature_c.
    parts = []

    # Surface description uses overall quality + representative's snow amounts
    surface = _describe_surface(representative, quality_override=overall_quality)
    if surface:
        parts.append(surface)

    # Fresh snow context from representative
    fresh = _describe_fresh_snow(representative)
    if fresh:
        parts.append(fresh)

    # Temperature from representative (matches temperature_c in API response)
    temp = _describe_temperature(representative)
    if temp:
        parts.append(temp)

    # Base depth from representative
    base_desc = _describe_base(representative)
    if base_desc:
        parts.append(base_desc)

    # Forecast from representative
    forecast = _describe_forecast(representative)
    if forecast:
        parts.append(forecast)

    return " ".join(parts) if parts else _default_explanation(overall_quality)


def _norm_quality(q: SnowQuality | str) -> SnowQuality:
    """Normalize quality to SnowQuality enum."""
    return SnowQuality(q) if isinstance(q, str) else q


def _brief_summit(condition: WeatherCondition) -> str:
    """Brief description of summit conditions for mixed-elevation text."""
    quality = _norm_quality(condition.snow_quality)
    fresh_cm = condition.fresh_snow_cm or 0
    snow_24h = condition.snowfall_24h_cm or 0

    if quality == SnowQuality.EXCELLENT:
        if snow_24h >= 10:
            return f"Fresh powder at summit ({snow_24h:.0f}cm in 24h)"
        if fresh_cm >= 8:
            return f"Fresh powder at summit ({fresh_cm:.0f}cm uncompacted)"
        return "Fresh powder at summit"

    if quality == SnowQuality.GOOD:
        temp = condition.current_temp_celsius
        is_cold = temp is not None and temp < -5
        if fresh_cm >= 30:
            return f"Good snow at summit ({fresh_cm:.0f}cm fresh)"
        if snow_24h >= 5:
            if is_cold:
                return f"Dry packed powder at summit ({snow_24h:.0f}cm recent)"
            return f"Soft surface at summit ({snow_24h:.0f}cm recent)"
        if is_cold:
            return "Good, dry packed powder at summit"
        return "Good, soft surface at summit"

    if quality == SnowQuality.FAIR:
        if fresh_cm >= 30:
            return f"Fair at summit ({fresh_cm:.0f}cm fresh)"
        if fresh_cm >= 3:
            return f"Some fresh snow at summit ({fresh_cm:.0f}cm)"
        return "Firm surface at summit"

    if quality == SnowQuality.POOR:
        return "Hard packed at summit"

    if quality == SnowQuality.BAD:
        return "Icy at summit"

    return ""


def _brief_lower_issue(condition: WeatherCondition) -> str:
    """Brief description of the issue at lower elevations."""
    quality = _norm_quality(condition.snow_quality)
    temp = condition.current_temp_celsius

    if quality in (SnowQuality.HORRIBLE, SnowQuality.BAD):
        if temp is not None and temp > 0:
            return f"icy at lower elevations ({temp:.0f}°C)"
        return "icy at lower elevations"

    if quality == SnowQuality.POOR:
        return "hard packed at lower elevations"

    if quality == SnowQuality.FAIR:
        return "firmer conditions at lower elevations"

    return "variable conditions at lower elevations"


def score_to_100(raw_score: float) -> int:
    """Convert ML model raw score (1.0-6.0) to a 0-100 scale.

    1.0 (horrible) -> 0
    6.0 (excellent) -> 100
    """
    return max(0, min(100, round((raw_score - 1.0) / 5.0 * 100)))
