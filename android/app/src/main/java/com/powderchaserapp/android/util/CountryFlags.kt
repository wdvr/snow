package com.powderchaserapp.android.util

/**
 * Converts a country code (ISO 3166-1 alpha-2) to a flag emoji.
 * Each letter is offset to the regional indicator symbol range.
 */
fun countryCodeToFlag(countryCode: String): String {
    if (countryCode.length != 2) return ""
    val first = Character.codePointAt(countryCode.uppercase(), 0) - 0x41 + 0x1F1E6
    val second = Character.codePointAt(countryCode.uppercase(), 1) - 0x41 + 0x1F1E6
    return String(Character.toChars(first)) + String(Character.toChars(second))
}

// Known base region prefixes (without sub-region suffix)
private val knownBaseRegions = setOf(
    "na_west", "na_rockies", "na_east",
    "alps", "scandinavia", "japan", "oceania", "south_america",
    "asia", "eastern_europe",
)

// US state abbreviations to full names
private val usStates = mapOf(
    "CA" to "California", "CO" to "Colorado", "UT" to "Utah",
    "WY" to "Wyoming", "MT" to "Montana", "ID" to "Idaho",
    "OR" to "Oregon", "WA" to "Washington", "NM" to "New Mexico",
    "VT" to "Vermont", "NH" to "New Hampshire", "ME" to "Maine",
    "NY" to "New York", "PA" to "Pennsylvania", "WV" to "West Virginia",
    "NC" to "North Carolina", "MI" to "Michigan", "WI" to "Wisconsin",
    "MN" to "Minnesota", "AK" to "Alaska", "NV" to "Nevada",
    "AZ" to "Arizona", "SD" to "South Dakota",
)

// Canadian province abbreviations to full names
private val canadianProvinces = mapOf(
    "BC" to "British Columbia", "AB" to "Alberta",
    "ON" to "Ontario", "QC" to "Quebec", "NB" to "New Brunswick",
    "NS" to "Nova Scotia",
)

// Base region display names
private val baseRegionNames = mapOf(
    "na_west" to "NA West Coast",
    "na_rockies" to "NA Rockies",
    "na_east" to "NA East Coast",
    "alps" to "European Alps",
    "scandinavia" to "Scandinavia",
    "japan" to "Japan",
    "oceania" to "Oceania",
    "south_america" to "South America",
    "asia" to "Asia",
    "eastern_europe" to "Eastern Europe",
)

/**
 * Returns the region display name for a given region code,
 * including support for compound keys like "na_west_BC" -> "NA West Coast (British Columbia)".
 */
fun regionDisplayName(region: String): String {
    val lower = region.lowercase()

    // Exact match first
    baseRegionNames[lower]?.let { return it }

    // Try compound key: find the longest matching base region prefix
    for (base in knownBaseRegions.sortedByDescending { it.length }) {
        if (lower.startsWith("${base}_")) {
            val suffix = region.substring(base.length + 1).uppercase()
            val baseName = baseRegionNames[base] ?: base

            // For NA regions, look up state/province name
            if (base.startsWith("na_")) {
                val stateName = usStates[suffix] ?: canadianProvinces[suffix]
                if (stateName != null) {
                    return "$baseName ($stateName)"
                }
            }

            // For non-NA compound keys (e.g., alps_FR), just use the base name
            // The country is already shown elsewhere
            return baseName
        }
    }

    return region.replaceFirstChar { it.uppercase() }
}

/**
 * Infers a ski region from a resort's country and region fields.
 */
fun inferRegion(country: String, region: String): String {
    return when (country.uppercase()) {
        "JP" -> "japan"
        "KR", "CN" -> "asia"
        "NZ", "AU" -> "oceania"
        "CL", "AR" -> "south_america"
        "NO", "SE", "FI" -> "scandinavia"
        "PL", "CZ", "SK", "RO", "BG" -> "eastern_europe"
        "FR", "CH", "AT", "IT", "DE", "SI", "ES", "AD" -> "alps"
        "US" -> when (region.uppercase()) {
            "CA", "OR", "WA" -> "na_west"
            "CO", "UT", "WY", "MT", "ID", "NM" -> "na_rockies"
            else -> "na_east"
        }
        "CA" -> when (region.uppercase()) {
            "BC" -> "na_west"
            "AB" -> "na_rockies"
            else -> "na_east"
        }
        else -> "alps"
    }
}
