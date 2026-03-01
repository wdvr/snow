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

    # 5. Wind/visibility context
    wind_vis = _describe_wind_visibility(condition)
    if wind_vis:
        parts.append(wind_vis)

    # 6. Forecast outlook
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

    if quality == SnowQuality.CHAMPAGNE_POWDER:
        if snow_24h >= 15:
            return f"Ultra-light champagne powder: {snow_24h:.0f}cm in the last 24 hours. Dry, cold, and deep."
        elif snow_24h >= 10:
            return f"Champagne powder: {snow_24h:.0f}cm of ultra-light snow in the last 24 hours."
        elif snow_48h >= 15:
            return f"Champagne powder: {snow_48h:.0f}cm of ultra-dry snow in the last 48 hours."
        elif fresh_cm >= 10:
            return f"Champagne powder: {fresh_cm:.0f}cm of ultra-light, dry snow."
        return "Champagne powder conditions — ultra-light, dry snow."

    if quality == SnowQuality.POWDER_DAY:
        if snow_24h >= 10:
            return f"Powder day: {snow_24h:.0f}cm of fresh snow in the last 24 hours."
        elif snow_48h >= 10:
            return f"Powder day: {snow_48h:.0f}cm of fresh snow in the last 48 hours."
        elif fresh_cm >= 7.6:
            return f"Powder day: {fresh_cm:.0f}cm of recent snow."
        return "Deep fresh powder conditions."

    if quality == SnowQuality.EXCELLENT:
        if snow_24h >= 10:
            return f"Fresh powder: {snow_24h:.0f}cm in the last 24 hours."
        elif snow_48h >= 10:
            return f"Fresh powder: {snow_48h:.0f}cm in the last 48 hours."
        elif fresh_cm >= 7.6:
            return f"Fresh powder: {fresh_cm:.0f}cm of recent snow."
        return "Fresh powder conditions."

    if quality == SnowQuality.GREAT:
        # Use temperature-aware descriptions: below -5°C snow is dry, not soft
        is_cold = temp is not None and temp < -5
        if snow_24h >= 5:
            if is_cold:
                return f"Dry packed powder with {snow_24h:.0f}cm of recent snow."
            return f"Soft surface with {snow_24h:.0f}cm of recent snow."
        elif fresh_cm >= 80:
            if hours_since and hours_since > 48:
                return "Deep snow cover — settled base with great coverage."
            return f"Deep base with {fresh_cm:.0f}cm of fresh snow."
        elif fresh_cm >= 5:
            if hours_since and hours_since > 48:
                return f"Settled powder: {fresh_cm:.0f}cm of snow, last snowfall {_format_hours(hours_since)} ago."
            return f"Good coverage with {fresh_cm:.0f}cm of fresh snow."
        if is_cold:
            return "Dry packed powder — good rideable surface."
        return "Soft, rideable surface."

    if quality == SnowQuality.GOOD:
        is_cold = temp is not None and temp < -5
        if snow_24h >= 5:
            if is_cold:
                return f"Dry packed powder with {snow_24h:.0f}cm of recent snow."
            return f"Good surface with {snow_24h:.0f}cm of recent snow."
        elif fresh_cm >= 30:
            if warming:
                return f"Good base ({fresh_cm:.0f}cm settled) but currently warming."
            if hours_since and hours_since > 48:
                return f"Deep snow cover with {fresh_cm:.0f}cm of settled snow."
            return f"Good base with {fresh_cm:.0f}cm of fresh snow."
        elif fresh_cm >= 5:
            if hours_since and hours_since > 48:
                return f"Solid conditions with {fresh_cm:.0f}cm of settled snow on a good base."
            return (
                f"Solid conditions with {fresh_cm:.0f}cm of fresh snow on a good base."
            )
        if is_cold:
            return "Solid groomed conditions — cold and dry."
        return "Solid groomed conditions."

    if quality == SnowQuality.DECENT:
        if fresh_cm >= 80:
            if hours_since and hours_since > 48:
                return "Deep snow cover — settled but substantial."
            return f"Substantial base with {fresh_cm:.0f}cm of fresh snow."
        elif hours_since and hours_since > 72 and fresh_cm > 5:
            return f"Packed powder: {fresh_cm:.0f}cm of aged snow (last snowfall {_format_hours(hours_since)} ago)."
        elif fresh_cm >= 30:
            if warming:
                return f"Good base ({fresh_cm:.0f}cm settled) but currently warming."
            if hours_since and hours_since > 48:
                return f"Good base with {fresh_cm:.0f}cm of settled snow."
            return f"Good base with {fresh_cm:.0f}cm of fresh snow."
        elif fresh_cm >= 2.5:
            if warming:
                if hours_since and hours_since > 48:
                    return f"Some settled snow ({fresh_cm:.0f}cm) but currently warming — surface softening."
                return f"Some fresh snow ({fresh_cm:.0f}cm) but currently warming — surface softening."
            if hours_since and hours_since > 48:
                return f"Some settled snow ({fresh_cm:.0f}cm) on a firm base."
            return f"Some fresh snow ({fresh_cm:.0f}cm) on a firm base."
        return "Firm, groomed-type surface with limited fresh snow."

    if quality == SnowQuality.MEDIOCRE:
        if fresh_cm >= 30:
            return f"Aging snow ({fresh_cm:.0f}cm) — firm, groomed-type surface."
        elif snow_24h >= 8:
            return f"Fresh snow ({snow_24h:.0f}cm/24h) on a warming base. Variable conditions."
        elif fresh_cm >= 2.5:
            return f"Some fresh snow ({fresh_cm:.0f}cm) on a firm base. Best on groomed runs."
        return "Firm surface with limited fresh snow. Stick to groomed runs."

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
        depth = condition.snow_depth_cm
        if temp > 5 and (depth is None or depth < 30):
            return (
                f"Not skiable: warm temperatures ({temp:.0f}°C) actively melting snow."
            )
        elif temp > 5 and depth is not None and depth >= 30:
            return f"Very poor conditions: warm ({temp:.0f}°C) and degrading fast despite {depth:.0f}cm base."
        elif depth is not None and depth >= 30:
            return f"Very poor conditions: icy, degraded surface despite {depth:.0f}cm base."
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


def _describe_wind_visibility(condition: WeatherCondition) -> str:
    """Describe wind and visibility conditions when notable, including score impact."""
    parts = []

    wind = condition.wind_speed_kmh
    gust = getattr(condition, "wind_gust_kmh", None)
    vis = getattr(condition, "visibility_m", None)

    if gust and gust > 60:
        parts.append(f"{gust:.0f} km/h gusts lower the score.")
    elif wind and wind > 40:
        parts.append(f"{wind:.0f} km/h wind lowers the score.")
    elif wind and wind > 25:
        parts.append(f"{wind:.0f} km/h wind decreases the score.")

    if vis is not None and vis < 500:
        parts.append("Very low visibility decreases the score.")
    elif vis is not None and vis < 1000:
        parts.append("Low visibility decreases the score.")

    return " ".join(parts)


def _default_explanation(quality: SnowQuality) -> str:
    """Fallback explanation when data is insufficient."""
    defaults = {
        SnowQuality.CHAMPAGNE_POWDER: "Champagne powder — ultra-light, dry snow.",
        SnowQuality.POWDER_DAY: "Powder day — deep fresh snow.",
        SnowQuality.EXCELLENT: "Excellent conditions with fresh powder.",
        SnowQuality.GREAT: "Great rideable conditions.",
        SnowQuality.GOOD: "Good conditions with solid base.",
        SnowQuality.DECENT: "Decent conditions. Groomed runs recommended.",
        SnowQuality.MEDIOCRE: "Mediocre conditions. Stick to groomed runs.",
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
    wind_gust_kmh: float | None = None,
    visibility_m: float | None = None,
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
    if q == SnowQuality.CHAMPAGNE_POWDER:
        if snowfall_cm >= 10:
            parts.append(
                f"{prefix}Champagne powder with {snowfall_cm:.0f}cm of ultra-light snow."
            )
        else:
            parts.append(f"{prefix}Champagne powder — ultra-light, dry snow.")
    elif q == SnowQuality.POWDER_DAY:
        if snowfall_cm >= 5:
            parts.append(f"{prefix}Powder day with {snowfall_cm:.0f}cm of fresh snow.")
        else:
            parts.append(f"{prefix}Deep fresh powder conditions.")
    elif q == SnowQuality.EXCELLENT:
        if snowfall_cm >= 5:
            parts.append(f"{prefix}Fresh powder with {snowfall_cm:.0f}cm of snowfall.")
        else:
            parts.append(f"{prefix}Excellent powder conditions.")
    elif q == SnowQuality.GREAT:
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
                parts.append(f"{prefix}Great, dry packed powder.")
            else:
                parts.append(f"{prefix}Great, soft rideable surface.")
    elif q == SnowQuality.GOOD:
        is_cold = temperature_c < -5
        if snowfall_cm >= 2:
            if is_cold:
                parts.append(
                    f"{prefix}Good conditions with {snowfall_cm:.0f}cm of recent snow."
                )
            else:
                parts.append(
                    f"{prefix}Good surface with {snowfall_cm:.0f}cm of recent snow."
                )
        else:
            if is_cold:
                parts.append(f"{prefix}Good, solid groomed conditions.")
            else:
                parts.append(f"{prefix}Good, solid rideable surface.")
    elif q == SnowQuality.DECENT:
        if snowfall_cm >= 1:
            parts.append(
                f"{prefix}Some fresh snow ({snowfall_cm:.0f}cm) on a firm base."
            )
        else:
            parts.append(f"{prefix}Firm, groomed-type surface.")
    elif q == SnowQuality.MEDIOCRE:
        parts.append(f"{prefix}Firm surface with limited fresh snow.")
    elif q == SnowQuality.POOR:
        parts.append(f"{prefix}Hard packed with limited fresh snow.")
    elif q == SnowQuality.BAD:
        parts.append(f"{prefix}Icy, refrozen surface.")
    elif q == SnowQuality.HORRIBLE:
        # Depth-aware logic matching _describe_surface() for HORRIBLE quality
        if temperature_c > 5 and (snow_depth_cm is None or snow_depth_cm < 30):
            parts.append(
                f"{prefix}Not skiable: warm temperatures ({temperature_c:.0f}\u00b0C) actively melting snow."
            )
        elif temperature_c > 5 and snow_depth_cm is not None and snow_depth_cm >= 30:
            parts.append(
                f"{prefix}Very poor conditions: warm ({temperature_c:.0f}\u00b0C) and degrading fast despite {snow_depth_cm:.0f}cm base."
            )
        elif snow_depth_cm is not None and snow_depth_cm >= 30:
            parts.append(
                f"{prefix}Very poor conditions: icy, degraded surface despite {snow_depth_cm:.0f}cm base."
            )
        else:
            parts.append(f"{prefix}Not skiable: insufficient snow cover.")
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
    if wind_gust_kmh and wind_gust_kmh > 60:
        parts.append(f"{wind_gust_kmh:.0f} km/h gusts lower the score.")
    elif wind_speed_kmh and wind_speed_kmh > 40:
        parts.append(f"{wind_speed_kmh:.0f} km/h wind lowers the score.")
    elif wind_speed_kmh and wind_speed_kmh > 25:
        parts.append(f"{wind_speed_kmh:.0f} km/h wind decreases the score.")

    # Visibility context
    if visibility_m is not None and visibility_m < 500:
        parts.append("Very low visibility decreases the score.")
    elif visibility_m is not None and visibility_m < 1000:
        parts.append("Low visibility decreases the score.")

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

    # Wind/visibility context from representative
    wind_vis = _describe_wind_visibility(representative)
    if wind_vis:
        parts.append(wind_vis)

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

    if quality in (SnowQuality.CHAMPAGNE_POWDER, SnowQuality.POWDER_DAY):
        if snow_24h >= 10:
            return f"Deep powder at summit ({snow_24h:.0f}cm in 24h)"
        if fresh_cm >= 8:
            return f"Deep powder at summit ({fresh_cm:.0f}cm recent)"
        return "Deep powder at summit"

    if quality == SnowQuality.EXCELLENT:
        if snow_24h >= 10:
            return f"Fresh powder at summit ({snow_24h:.0f}cm in 24h)"
        if fresh_cm >= 8:
            return f"Fresh powder at summit ({fresh_cm:.0f}cm recent)"
        return "Fresh powder at summit"

    if quality == SnowQuality.GREAT:
        temp = condition.current_temp_celsius
        is_cold = temp is not None and temp < -5
        if fresh_cm >= 30:
            return f"Great snow at summit ({fresh_cm:.0f}cm fresh)"
        if snow_24h >= 5:
            if is_cold:
                return f"Dry packed powder at summit ({snow_24h:.0f}cm recent)"
            return f"Soft surface at summit ({snow_24h:.0f}cm recent)"
        if is_cold:
            return "Great, dry packed powder at summit"
        return "Great, soft surface at summit"

    if quality == SnowQuality.GOOD:
        if fresh_cm >= 30:
            return f"Good snow at summit ({fresh_cm:.0f}cm fresh)"
        if fresh_cm >= 5:
            return f"Good conditions at summit ({fresh_cm:.0f}cm fresh)"
        return "Good conditions at summit"

    if quality == SnowQuality.DECENT:
        if fresh_cm >= 30:
            return f"Decent at summit ({fresh_cm:.0f}cm fresh)"
        if fresh_cm >= 3:
            return f"Some fresh snow at summit ({fresh_cm:.0f}cm)"
        return "Firm surface at summit"

    if quality == SnowQuality.MEDIOCRE:
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

    if quality in (SnowQuality.DECENT, SnowQuality.MEDIOCRE):
        return "firmer conditions at lower elevations"

    return "variable conditions at lower elevations"


def score_to_100(raw_score: float) -> int:
    """Convert ML model raw score (1.0-6.0) to a 0-100 scale.

    Uses piecewise-linear calibration instead of naive linear mapping.
    The model's training data clusters around 3.0-4.0 (average groomed days),
    and linear mapping places those at 40-60 which feels too harsh — a typical
    groomed day with cold temps and deep base is perfectly enjoyable skiing.

    Calibration targets:
      1.0 ->  0  (not skiable)
      2.5 -> 22  (icy, minimal fresh)
      3.5 -> 65  (average groomed, good base, cold)
      4.5 -> 83  (recent snow, cold preservation)
      5.5 -> 95  (powder day)
      6.0 -> 100 (epic)
    """
    breakpoints = [
        (1.0, 0),
        (2.5, 22),
        (3.5, 65),
        (4.5, 83),
        (5.5, 95),
        (6.0, 100),
    ]
    raw_score = max(1.0, min(6.0, raw_score))
    for i in range(len(breakpoints) - 1):
        r1, t1 = breakpoints[i]
        r2, t2 = breakpoints[i + 1]
        if raw_score <= r2:
            frac = (raw_score - r1) / (r2 - r1)
            return max(0, min(100, round(t1 + frac * (t2 - t1))))
    return 100


def generate_score_change_reason(
    current: dict,
    previous: dict | None,
) -> str | None:
    """Generate a concise reason explaining WHY the score changed vs the previous period.

    Compares two consecutive timeline points and identifies the dominant factor
    driving the score change. Returns None for the first point or when the score
    is unchanged.

    Args:
        current: Current timeline point dict with keys like temperature_c,
                 snowfall_cm, snow_depth_cm, wind_speed_kmh, snow_score, etc.
        previous: Previous timeline point dict, or None for the first point.

    Returns:
        A short human-readable string like "+5cm fresh snow improves conditions",
        or None if there is no previous point or the score didn't change.
    """
    if previous is None:
        return None

    cur_score = current.get("snow_score")
    prev_score = previous.get("snow_score")

    if cur_score is None or prev_score is None:
        return None

    score_delta = cur_score - prev_score

    if score_delta == 0:
        return None

    # Extract weather values
    cur_temp = current.get("temperature_c", 0.0)
    prev_temp = previous.get("temperature_c", 0.0)
    cur_snowfall = current.get("snowfall_cm", 0.0)
    prev_snowfall = previous.get("snowfall_cm", 0.0)
    cur_depth = current.get("snow_depth_cm")
    prev_depth = previous.get("snow_depth_cm")
    cur_wind = current.get("wind_speed_kmh") or 0.0
    prev_wind = previous.get("wind_speed_kmh") or 0.0
    cur_gust = current.get("wind_gust_kmh") or 0.0
    prev_gust = previous.get("wind_gust_kmh") or 0.0
    cur_vis = current.get("visibility_m")
    prev_vis = previous.get("visibility_m")
    cur_time = current.get("time_label", "")

    temp_delta = cur_temp - prev_temp
    wind_delta = cur_wind - prev_wind
    gust_delta = cur_gust - prev_gust
    depth_delta = (
        (cur_depth - prev_depth)
        if cur_depth is not None and prev_depth is not None
        else 0.0
    )

    improving = score_delta > 0
    arrow = "+" if score_delta > 0 else ""

    # Score magnitude descriptors
    abs_delta = abs(score_delta)
    if abs_delta >= 15:
        magnitude = "significantly "
    elif abs_delta >= 5:
        magnitude = ""
    else:
        magnitude = "slightly "

    # --- Identify the dominant factor ---

    # 1. Fresh snowfall is the strongest positive signal (lowered from 2.0cm)
    if cur_snowfall >= 0.5 and improving:
        if cur_snowfall >= 5.0:
            return f"+{cur_snowfall:.0f}cm fresh snow {magnitude}improves conditions"
        return f"+{cur_snowfall:.1f}cm fresh snow {magnitude}improves conditions"

    # 2. Temperature crossing freezing point
    if prev_temp <= 0 and cur_temp > 2:
        return f"Warming to {cur_temp:.0f}\u00b0C {magnitude}softens snow"
    if prev_temp > 0 and cur_temp <= -2:
        return f"Cooling to {cur_temp:.0f}\u00b0C {magnitude}firms up snow"

    # 3. Refreezing after warm period (temp drops below zero after being above)
    if prev_temp > 0 and cur_temp < 0 and not improving:
        return f"Refreezing at {cur_temp:.0f}\u00b0C creates icy surface"

    # 4. Wind — absolute high wind or significant change (lowered thresholds)
    if cur_gust > 25 and not improving:
        return f"Gusts of {cur_gust:.0f} km/h {magnitude}reduce score"
    if gust_delta > 10 and not improving:
        return f"Wind gusts up to {cur_gust:.0f} km/h {magnitude}worsen conditions"
    if wind_delta > 5 and cur_wind > 15 and not improving:
        return f"Wind increasing to {cur_wind:.0f} km/h {magnitude}worsens conditions"
    if wind_delta < -5 and improving:
        return f"Wind easing to {cur_wind:.0f} km/h {magnitude}improves conditions"
    if gust_delta < -10 and improving:
        return f"Wind gusts easing {magnitude}improves conditions"

    # 5. Daytime warming — afternoon temp rise worsens
    if (
        cur_time in ("midday", "afternoon")
        and temp_delta > 2
        and not improving
        and cur_temp > -2
    ):
        return f"Daytime warming to {cur_temp:.0f}\u00b0C {magnitude}softens conditions"

    # 6. Overnight cooling — morning temp drop improves
    if cur_time == "morning" and temp_delta < -2 and improving and cur_temp < 0:
        return f"Overnight cooling to {cur_temp:.0f}\u00b0C {magnitude}firms up snow"

    # 7. Significant temperature change (only blame warming near/above freezing)
    if temp_delta > 2 and not improving and cur_temp > -3:
        return f"Warming to {cur_temp:.0f}\u00b0C {magnitude}softens conditions"
    if temp_delta < -5 and cur_temp < -15:
        return f"Extreme cold ({cur_temp:.0f}\u00b0C) {magnitude}worsens conditions"
    if temp_delta < -2 and improving and cur_temp < 0:
        return f"Cooling to {cur_temp:.0f}\u00b0C {magnitude}improves conditions"

    # 8. Snow depth loss (lowered from -10 to -5)
    if depth_delta < -5 and not improving:
        return (
            f"Snow depth dropping ({depth_delta:.0f}cm) {magnitude}worsens conditions"
        )

    # 9. Visibility changes
    if cur_vis is not None and prev_vis is not None:
        if cur_vis < 1000 and prev_vis >= 2000 and not improving:
            return (
                f"Visibility dropping to {cur_vis:.0f}m {magnitude}worsens conditions"
            )
        if cur_vis >= 2000 and prev_vis < 1000 and improving:
            return f"Visibility improving {magnitude}improves conditions"

    # 10. Snowfall stopped (previous had snow, current doesn't; lowered from 2.0)
    if prev_snowfall >= 0.5 and cur_snowfall < 0.2 and not improving:
        return f"Snowfall stopped; conditions {magnitude}settling"

    # 11. Snow aging — no fresh snow and score drops
    if cur_snowfall < 0.2 and prev_snowfall < 0.2 and not improving:
        return f"No fresh snow; conditions {magnitude}settling"

    # 12. Smart fallback — identify the largest changing factor
    # Each factor is (magnitude, description, is_negative_for_skiing)
    # is_negative = True means this factor worsens conditions
    factors: list[tuple[float, str, bool]] = []
    # Temperature change relative importance (each degree matters)
    if abs(temp_delta) > 0.5:
        desc = f"{cur_temp:.0f}\u00b0C" if cur_temp != 0 else "0\u00b0C"
        if temp_delta > 0:
            # Warming is only negative near/above freezing; sub-zero warming is neutral
            factors.append((abs(temp_delta) * 3, f"warming to {desc}", cur_temp > -3))
        else:
            factors.append((abs(temp_delta) * 3, f"cooling to {desc}", False))
    # Wind change (only mention if wind is actually significant)
    if abs(wind_delta) > 1 and max(cur_wind, prev_wind) > 10:
        if wind_delta > 0:
            factors.append((abs(wind_delta), f"wind up to {cur_wind:.0f} km/h", True))
        else:
            factors.append(
                (abs(wind_delta), f"wind easing to {cur_wind:.0f} km/h", False)
            )
    # Gust change (only if gusts are meaningful)
    if abs(gust_delta) > 2 and max(cur_gust, prev_gust) > 15:
        if gust_delta > 0:
            factors.append(
                (abs(gust_delta) * 0.8, f"gusts up to {cur_gust:.0f} km/h", True)
            )
        else:
            factors.append(
                (abs(gust_delta) * 0.8, f"gusts easing to {cur_gust:.0f} km/h", False)
            )
    # Visibility change (only for meaningful ranges, not 19860m)
    if cur_vis is not None and prev_vis is not None and prev_vis > 0:
        vis_ratio = abs(cur_vis - prev_vis) / max(prev_vis, 1)
        if vis_ratio > 0.2 and min(cur_vis, prev_vis) < 5000:
            if cur_vis < prev_vis:
                factors.append(
                    (vis_ratio * 10, f"visibility dropping to {cur_vis:.0f}m", True)
                )
            else:
                factors.append(
                    (vis_ratio * 10, f"visibility improving to {cur_vis:.0f}m", False)
                )
    # Snowfall delta
    snowfall_delta = cur_snowfall - prev_snowfall
    if abs(snowfall_delta) > 0.1:
        if snowfall_delta < 0:
            factors.append((abs(snowfall_delta) * 5, "snowfall easing", True))
        else:
            factors.append(
                (abs(snowfall_delta) * 5, f"+{cur_snowfall:.1f}cm snowfall", False)
            )

    if factors:
        # Prefer factors whose direction aligns with the score change
        aligned = [
            f for f in factors if (f[2] and not improving) or (not f[2] and improving)
        ]
        if aligned:
            aligned.sort(key=lambda x: x[0], reverse=True)
            top_factor = aligned[0][1]
            top_factor_cap = top_factor[0].upper() + top_factor[1:]
            if improving:
                return f"{top_factor_cap} {magnitude}improves conditions"
            else:
                return f"{top_factor_cap} {magnitude}worsens conditions"
        # No aligned factors — don't misattribute (e.g. "gusts improve conditions")

    # 13. Ultimate fallback (should rarely be reached)
    if improving:
        return f"Conditions {magnitude}improving ({arrow}{score_delta} pts)"
    else:
        return f"Conditions {magnitude}declining ({score_delta} pts)"
