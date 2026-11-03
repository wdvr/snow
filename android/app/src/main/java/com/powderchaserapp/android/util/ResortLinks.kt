package com.powderchaserapp.android.util

import com.powderchaserapp.android.data.api.FeedbackSubmission

/**
 * Trail map URL handling, matching iOS (ResortDetailView) and web (TrailMapCard).
 *
 * Direct image URLs (e.g. snow-forecast piste maps) open in the in-app zoomable
 * viewer. Anything else (e.g. skiresort.info interactive trail map pages) opens
 * in a browser tab.
 */
object TrailMapUrl {
    private val imageExtensions = listOf(".jpg", ".jpeg", ".png", ".webp", ".gif")

    fun isDirectImage(url: String): Boolean {
        val path = url.substringBefore('#').substringBefore('?').lowercase()
        return imageExtensions.any { path.endsWith(it) }
    }
}

/**
 * OpenSnowMap piste tiles, the same overlay iOS (MKTileOverlay) and web use.
 * Tiles only exist at zoom 12 to 18.
 */
object OpenSnowMapTiles {
    const val MIN_ZOOM = 12
    const val MAX_ZOOM = 18
    const val TILE_SIZE = 256
    const val ATTRIBUTION = "Pistes © OpenSnowMap.org, data © OpenStreetMap contributors"

    fun tileUrl(x: Int, y: Int, zoom: Int): String? {
        if (zoom < MIN_ZOOM || zoom > MAX_ZOOM) return null
        return "https://tiles.opensnowmap.org/pistes/$zoom/$x/$y.png"
    }
}

/**
 * Builds the "Suggest an Edit" feedback payload in the same format as iOS
 * (SuggestEditView) and web (SuggestEditModal), within the backend limits
 * (subject <= 100 chars, message 10..2000 chars).
 */
object ResortEditSuggestion {
    const val MIN_SUGGESTION_LENGTH = 10
    const val MAX_SUGGESTION_LENGTH = 1500
    private const val MAX_SUBJECT_LENGTH = 100
    private const val MAX_MESSAGE_LENGTH = 2000

    val sections = listOf(
        "Elevation data",
        "Lift count / trail count",
        "Location / region",
        "Pass info (Epic/Ikon)",
        "Website / webcam URL",
        "Trail map",
        "Other",
    )

    fun isValid(section: String, suggestion: String): Boolean =
        section.isNotBlank() && suggestion.trim().length >= MIN_SUGGESTION_LENGTH

    fun build(
        resortId: String,
        resortName: String,
        section: String,
        suggestion: String,
        appVersion: String,
        buildNumber: String,
        deviceModel: String,
        osVersion: String,
    ): FeedbackSubmission {
        val cleanSection = section.trim()
        val message = buildString {
            append("[Resort Edit Suggestion]\n")
            append("Resort: $resortName ($resortId)\n")
            append("Section: $cleanSection\n\n")
            append("Suggested correction:\n")
            append(suggestion.trim())
        }
        return FeedbackSubmission(
            subject = "Resort Edit: $resortName - $cleanSection".take(MAX_SUBJECT_LENGTH),
            message = message.take(MAX_MESSAGE_LENGTH),
            appVersion = appVersion.take(20),
            buildNumber = buildNumber.take(20),
            deviceModel = deviceModel.take(50),
            osVersion = osVersion.take(20),
        )
    }
}
