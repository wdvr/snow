package com.powderchaserapp.android.ui.components

import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage

private val SKIP_WORDS = setOf("ski", "resort", "mountain", "area")

/**
 * Derives initials from a resort name by taking the first letter of the first two
 * significant words (skipping common filler words like "ski", "resort", etc.).
 */
private fun resortInitials(name: String): String {
    val words = name.split(" ", "-")
        .filter { it.isNotBlank() && it.lowercase() !in SKIP_WORDS }
    return when {
        words.size >= 2 -> "${words[0].first().uppercaseChar()}${words[1].first().uppercaseChar()}"
        words.size == 1 -> words[0].take(2).uppercase()
        else -> name.take(2).uppercase()
    }
}

/**
 * Builds a favicon URL from a resort's official website using the Google Favicon API.
 * Returns null if the website is null or blank.
 */
private fun faviconUrl(officialWebsite: String?): String? {
    if (officialWebsite.isNullOrBlank()) return null
    val hostname = try {
        Uri.parse(officialWebsite).host
            ?: officialWebsite.removePrefix("https://").removePrefix("http://").split("/").first()
    } catch (_: Exception) {
        officialWebsite.removePrefix("https://").removePrefix("http://").split("/").first()
    }
    if (hostname.isBlank()) return null
    return "https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://$hostname&size=128"
}

/**
 * Displays a resort logo (favicon from the resort's website) with an initials fallback.
 *
 * @param resortName The resort name, used for the initials fallback.
 * @param officialWebsite The resort's official website URL.
 * @param size The size of the logo in dp.
 */
@Composable
fun ResortLogo(
    resortName: String,
    officialWebsite: String?,
    logoUrl: String? = null,
    size: Dp,
    modifier: Modifier = Modifier,
) {
    val url = remember(logoUrl, officialWebsite) { logoUrl ?: faviconUrl(officialWebsite) }
    val initials = remember(resortName) { resortInitials(resortName) }
    val shape = RoundedCornerShape(8.dp)
    val fontSize = (size.value * 0.38f).sp

    Box(
        modifier = modifier
            .size(size)
            .clip(shape),
        contentAlignment = Alignment.Center,
    ) {
        // Always show fallback behind the image so there's no flash of empty space
        Box(
            modifier = Modifier
                .matchParentSize()
                .background(
                    brush = Brush.linearGradient(
                        colors = listOf(Color(0xFF1A73E8), Color(0xFF00BCD4)),
                    ),
                    shape = shape,
                ),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                text = initials,
                color = Color.White,
                fontSize = fontSize,
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.labelSmall,
            )
        }

        if (url != null) {
            AsyncImage(
                model = url,
                contentDescription = "$resortName logo",
                modifier = Modifier
                    .matchParentSize()
                    .clip(shape),
                contentScale = ContentScale.Crop,
            )
        }
    }
}
