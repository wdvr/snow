package com.powderchaserapp.android

import com.powderchaserapp.android.util.OpenSnowMapTiles
import com.powderchaserapp.android.util.ResortEditSuggestion
import com.powderchaserapp.android.util.TrailMapUrl
import org.junit.Assert.*
import org.junit.Test

class ResortLinksTest {

    // =========================================================================
    // Trail map URL detection (#187)
    // =========================================================================

    @Test
    fun `direct image urls open in app`() {
        assertTrue(TrailMapUrl.isDirectImage("https://www.snow-forecast.com/pistemaps/Alyeska-Resort_pistemap.jpg"))
        assertTrue(TrailMapUrl.isDirectImage("https://example.com/map.PNG"))
        assertTrue(TrailMapUrl.isDirectImage("https://example.com/map.jpeg?v=2"))
        assertTrue(TrailMapUrl.isDirectImage("https://example.com/map.webp#top"))
    }

    @Test
    fun `page urls open in browser`() {
        assertFalse(TrailMapUrl.isDirectImage("https://www.skiresort.info/ski-resort/jasna-chopok/trail-map/"))
        assertFalse(TrailMapUrl.isDirectImage("https://example.com/trailmap.pdf"))
        assertFalse(TrailMapUrl.isDirectImage("https://example.com/jpg-maps/index.html"))
    }

    // =========================================================================
    // OpenSnowMap piste tiles (#188)
    // =========================================================================

    @Test
    fun `tile url within zoom range`() {
        assertEquals(
            "https://tiles.opensnowmap.org/pistes/14/8521/5773.png",
            OpenSnowMapTiles.tileUrl(8521, 5773, 14),
        )
    }

    @Test
    fun `no tiles outside zoom range`() {
        assertNull(OpenSnowMapTiles.tileUrl(1, 1, OpenSnowMapTiles.MIN_ZOOM - 1))
        assertNull(OpenSnowMapTiles.tileUrl(1, 1, OpenSnowMapTiles.MAX_ZOOM + 1))
        assertNotNull(OpenSnowMapTiles.tileUrl(1, 1, OpenSnowMapTiles.MIN_ZOOM))
        assertNotNull(OpenSnowMapTiles.tileUrl(1, 1, OpenSnowMapTiles.MAX_ZOOM))
    }

    // =========================================================================
    // Suggest an Edit payload (#189)
    // =========================================================================

    private fun build(section: String = "Elevation data", suggestion: String = "Top elevation is 2024 m, not 2004 m.") =
        ResortEditSuggestion.build(
            resortId = "jasna",
            resortName = "Jasna Nizke Tatry",
            section = section,
            suggestion = suggestion,
            appVersion = "1.1.0",
            buildNumber = "2",
            deviceModel = "Pixel 9",
            osVersion = "15",
        )

    @Test
    fun `payload matches ios and web format`() {
        val payload = build()
        assertEquals("Resort Edit: Jasna Nizke Tatry - Elevation data", payload.subject)
        assertTrue(payload.message.startsWith("[Resort Edit Suggestion]\nResort: Jasna Nizke Tatry (jasna)\nSection: Elevation data\n"))
        assertTrue(payload.message.endsWith("Suggested correction:\nTop elevation is 2024 m, not 2004 m."))
        assertEquals("15", payload.osVersion)
    }

    @Test
    fun `payload respects backend limits`() {
        val payload = build(section = "x".repeat(300), suggestion = "y".repeat(5000))
        assertTrue(payload.subject.length <= 100)
        assertTrue(payload.message.length <= 2000)
    }

    @Test
    fun `validation requires section and ten characters`() {
        assertTrue(ResortEditSuggestion.isValid("Other", "0123456789"))
        assertFalse(ResortEditSuggestion.isValid("", "0123456789"))
        assertFalse(ResortEditSuggestion.isValid("Other", "   short   "))
    }
}
