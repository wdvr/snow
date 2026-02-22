package com.powderchaserapp.android.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

private val LightColorScheme = lightColorScheme(
    primary = SnowColors.PrimaryLight,
    onPrimary = SnowColors.OnPrimaryLight,
    secondary = SnowColors.SecondaryLight,
    tertiary = SnowColors.TertiaryLight,
    background = SnowColors.BackgroundLight,
    surface = SnowColors.SurfaceLight,
    surfaceVariant = SnowColors.SurfaceVariantLight,
)

private val DarkColorScheme = darkColorScheme(
    primary = SnowColors.PrimaryDark,
    onPrimary = SnowColors.OnPrimaryDark,
    secondary = SnowColors.SecondaryDark,
    tertiary = SnowColors.TertiaryDark,
    background = SnowColors.BackgroundDark,
    surface = SnowColors.SurfaceDark,
    surfaceVariant = SnowColors.SurfaceVariantDark,
)

@Composable
fun PowderChaserTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit,
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content,
    )
}
