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

    // Snow quality colors
    val QualityExcellent = Color(0xFF00A65A)
    val QualityGood = Color(0xFF34C759)
    val QualityFair = Color(0xFFFF9500)
    val QualityPoor = Color(0xFFFF9500)
    val QualityBad = Color(0xFFFF3B30)
    val QualityHorrible = Color(0xFF8E8E93)
    val QualityUnknown = Color(0xFF8E8E93)

    // Functional
    val SnowWhite = Color(0xFFF0F4FA)
    val IceBlue = Color(0xFF69B4F5)
    val MountainGray = Color(0xFF6E7B8B)
    val PineGreen = Color(0xFF2D5016)
    val SunsetOrange = Color(0xFFFF6B35)

    // Elevation colors
    val ElevationBase = Color(0xFF8BC34A)
    val ElevationMid = Color(0xFF42A5F5)
    val ElevationTop = Color(0xFF7E57C2)
}

fun snowQualityColor(quality: String): Color {
    return when (quality) {
        "excellent" -> SnowColors.QualityExcellent
        "good" -> SnowColors.QualityGood
        "fair" -> SnowColors.QualityFair
        "poor" -> SnowColors.QualityPoor
        "slushy" -> SnowColors.QualityFair
        "bad" -> SnowColors.QualityBad
        "horrible" -> SnowColors.QualityHorrible
        else -> SnowColors.QualityUnknown
    }
}
