package com.powderchaserapp.android.ui.theme

import androidx.compose.ui.graphics.Color

// Snow/Winter Color Palette
object SnowColors {
    // Primary - icy blue
    val PrimaryLight = Color(0xFF1A73E8)
    val PrimaryDark = Color(0xFF8AB4F8)
    val OnPrimaryLight = Color(0xFFFFFFFF)
    val OnPrimaryDark = Color(0xFF003A70)

    // Secondary - powder blue
    val SecondaryLight = Color(0xFF5E97C5)
    val SecondaryDark = Color(0xFF93C5E8)

    // Tertiary - fresh snow accent
    val TertiaryLight = Color(0xFF6C5E9B)
    val TertiaryDark = Color(0xFFCABEFF)

    // Background
    val BackgroundLight = Color(0xFFF8FAFD)
    val BackgroundDark = Color(0xFF121821)
    val SurfaceLight = Color(0xFFFFFFFF)
    val SurfaceDark = Color(0xFF1B2331)

    // Surface variants
    val SurfaceVariantLight = Color(0xFFE1E6EF)
    val SurfaceVariantDark = Color(0xFF3B4354)

    // Snow quality colors (10-level scale)
    val QualityChampagnePowder = Color(0xFF6366F1) // Indigo — the best
    val QualityPowderDay = Color(0xFF3B82F6)       // Blue — deep fresh
    val QualityExcellent = Color(0xFF00A65A)        // Emerald
    val QualityGreat = Color(0xFF22C55E)            // Green
    val QualityGood = Color(0xFF34C759)             // Light green
    val QualityDecent = Color(0xFFA3E635)           // Lime
    val QualityMediocre = Color(0xFFEAB308)         // Yellow
    val QualityFair = Color(0xFFFF9500)             // Orange
    val QualityPoor = Color(0xFFFF9500)             // Orange
    val QualitySlushy = Color(0xFFF97316)           // Dark orange
    val QualityBad = Color(0xFFFF3B30)              // Red
    val QualityHorrible = Color(0xFF8E8E93)         // Gray
    val QualityUnknown = Color(0xFF8E8E93)          // Gray

    // Functional
    val SnowWhite = Color(0xFFF0F4FA)
    val IceBlue = Color(0xFF69B4F5)
    val MountainGray = Color(0xFF6E7B8B)
    val PineGreen = Color(0xFF2D5016)
    val SunsetOrange = Color(0xFFFF6B35)

    // Pass badge colors
    val IndyGreen = Color(0xFF2E7D32)

    // Elevation colors
    val ElevationBase = Color(0xFF8BC34A)
    val ElevationMid = Color(0xFF42A5F5)
    val ElevationTop = Color(0xFF7E57C2)
}

fun snowQualityColor(quality: String): Color {
    return when (quality) {
        "champagne_powder" -> SnowColors.QualityChampagnePowder
        "powder_day" -> SnowColors.QualityPowderDay
        "excellent" -> SnowColors.QualityExcellent
        "great" -> SnowColors.QualityGreat
        "good" -> SnowColors.QualityGood
        "decent" -> SnowColors.QualityDecent
        "mediocre" -> SnowColors.QualityMediocre
        "fair" -> SnowColors.QualityFair
        "poor" -> SnowColors.QualityPoor
        "slushy" -> SnowColors.QualitySlushy
        "bad" -> SnowColors.QualityBad
        "horrible" -> SnowColors.QualityHorrible
        else -> SnowColors.QualityUnknown
    }
}

fun visibilityCategoryColor(category: com.powderchaserapp.android.data.api.VisibilityCategory): Color {
    return when (category) {
        com.powderchaserapp.android.data.api.VisibilityCategory.VERY_POOR -> SnowColors.QualityBad      // red
        com.powderchaserapp.android.data.api.VisibilityCategory.POOR -> SnowColors.SunsetOrange          // orange
        com.powderchaserapp.android.data.api.VisibilityCategory.LOW -> Color(0xFFFFCC00)                  // yellow
        com.powderchaserapp.android.data.api.VisibilityCategory.MODERATE -> SnowColors.MountainGray      // secondary text color
        com.powderchaserapp.android.data.api.VisibilityCategory.GOOD -> SnowColors.QualityGood           // green
    }
}
