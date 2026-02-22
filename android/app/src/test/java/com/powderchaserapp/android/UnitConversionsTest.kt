package com.powderchaserapp.android

import com.powderchaserapp.android.util.UnitConversions
import org.junit.Assert.*
import org.junit.Test

class UnitConversionsTest {

    // =========================================================================
    // Temperature
    // =========================================================================

    @Test
    fun `celsius to fahrenheit conversion`() {
        assertEquals(32.0, UnitConversions.celsiusToFahrenheit(0.0), 0.001)
        assertEquals(212.0, UnitConversions.celsiusToFahrenheit(100.0), 0.001)
        assertEquals(-40.0, UnitConversions.celsiusToFahrenheit(-40.0), 0.001)
        assertEquals(14.0, UnitConversions.celsiusToFahrenheit(-10.0), 0.001)
    }

    @Test
    fun `format temperature celsius`() {
        assertEquals("-5\u00B0C", UnitConversions.formatTemperature(-5.0, useMetric = true))
        assertEquals("0\u00B0C", UnitConversions.formatTemperature(0.0, useMetric = true))
        assertEquals("10\u00B0C", UnitConversions.formatTemperature(10.0, useMetric = true))
    }

    @Test
    fun `format temperature fahrenheit`() {
        assertEquals("23\u00B0F", UnitConversions.formatTemperature(-5.0, useMetric = false))
        assertEquals("32\u00B0F", UnitConversions.formatTemperature(0.0, useMetric = false))
    }

    // =========================================================================
    // Distance
    // =========================================================================

    @Test
    fun `km to miles conversion`() {
        assertEquals(0.621371, UnitConversions.kmToMiles(1.0), 0.001)
        assertEquals(62.137, UnitConversions.kmToMiles(100.0), 0.1)
    }

    @Test
    fun `format distance metric`() {
        assertEquals("500 m", UnitConversions.formatDistance(0.5, useMetric = true))
        assertEquals("5.0 km", UnitConversions.formatDistance(5.0, useMetric = true))
        assertEquals("50 km", UnitConversions.formatDistance(50.0, useMetric = true))
    }

    @Test
    fun `format distance imperial`() {
        val result = UnitConversions.formatDistance(10.0, useMetric = false)
        assertTrue(result.contains("mi"))
    }

    // =========================================================================
    // Snow Depth
    // =========================================================================

    @Test
    fun `cm to inches conversion`() {
        assertEquals(1.0, UnitConversions.cmToInches(2.54), 0.001)
        assertEquals(3.937, UnitConversions.cmToInches(10.0), 0.01)
    }

    @Test
    fun `format snow metric`() {
        assertEquals("20 cm", UnitConversions.formatSnow(20.0, useMetric = true))
        assertEquals("0 cm", UnitConversions.formatSnow(0.0, useMetric = true))
        assertEquals("0.5 cm", UnitConversions.formatSnow(0.5, useMetric = true))
    }

    @Test
    fun `format snow imperial`() {
        val result = UnitConversions.formatSnow(20.0, useMetric = false)
        assertTrue(result.contains("\""))
    }

    @Test
    fun `format snow short metric`() {
        assertEquals("20cm", UnitConversions.formatSnowShort(20.0, useMetric = true))
    }

    @Test
    fun `format snow short imperial`() {
        val result = UnitConversions.formatSnowShort(20.0, useMetric = false)
        assertTrue(result.contains("\""))
    }

    // =========================================================================
    // Wind Speed
    // =========================================================================

    @Test
    fun `kmh to mph conversion`() {
        assertEquals(0.621371, UnitConversions.kmhToMph(1.0), 0.001)
    }

    @Test
    fun `format wind speed metric`() {
        assertEquals("30 km/h", UnitConversions.formatWindSpeed(30.0, useMetric = true))
    }

    @Test
    fun `format wind speed imperial`() {
        val result = UnitConversions.formatWindSpeed(30.0, useMetric = false)
        assertTrue(result.contains("mph"))
    }

    // =========================================================================
    // Elevation
    // =========================================================================

    @Test
    fun `meters to feet conversion`() {
        assertEquals(3280.84, UnitConversions.metersToFeet(1000.0), 0.1)
    }

    @Test
    fun `format elevation metric`() {
        assertEquals("2000m", UnitConversions.formatElevation(2000.0, useMetric = true))
    }

    @Test
    fun `format elevation imperial`() {
        val result = UnitConversions.formatElevation(2000.0, useMetric = false)
        assertTrue(result.contains("ft"))
    }
}
