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

/**
 * Returns the region display name for a given region code.
 */
fun regionDisplayName(region: String): String {
    return when (region.lowercase()) {
        "na_west" -> "NA West Coast"
        "na_rockies" -> "NA Rockies"
        "na_east" -> "NA East Coast"
        "alps" -> "European Alps"
        "scandinavia" -> "Scandinavia"
        "japan" -> "Japan"
        "oceania" -> "Oceania"
        "south_america" -> "South America"
        else -> region.replaceFirstChar { it.uppercase() }
    }
}

/**
 * Infers a ski region from a resort's country and region fields.
 */
fun inferRegion(country: String, region: String): String {
    return when (country.uppercase()) {
        "JP" -> "japan"
        "NZ", "AU" -> "oceania"
        "CL", "AR" -> "south_america"
        "NO", "SE", "FI" -> "scandinavia"
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
