package com.powderchaserapp.android

import com.powderchaserapp.android.util.countryCodeToFlag
import com.powderchaserapp.android.util.inferRegion
import com.powderchaserapp.android.util.regionDisplayName
import org.junit.Assert.*
import org.junit.Test

class CountryFlagsTest {

    // =========================================================================
    // Country Code to Flag Emoji
    // =========================================================================

    @Test
    fun `country code US produces US flag`() {
        val flag = countryCodeToFlag("US")
        assertEquals("\uD83C\uDDFA\uD83C\uDDF8", flag)
    }

    @Test
    fun `country code CA produces CA flag`() {
        val flag = countryCodeToFlag("CA")
        assertEquals("\uD83C\uDDE8\uD83C\uDDE6", flag)
    }

    @Test
    fun `country code JP produces JP flag`() {
        val flag = countryCodeToFlag("JP")
        assertEquals("\uD83C\uDDEF\uD83C\uDDF5", flag)
    }

    @Test
    fun `lowercase country code works`() {
        val flag = countryCodeToFlag("us")
        assertEquals("\uD83C\uDDFA\uD83C\uDDF8", flag)
    }

    @Test
    fun `invalid length returns empty string`() {
        assertEquals("", countryCodeToFlag(""))
        assertEquals("", countryCodeToFlag("A"))
        assertEquals("", countryCodeToFlag("USA"))
    }

    // =========================================================================
    // Region Display Names
    // =========================================================================

    @Test
    fun `region display names are correct`() {
        assertEquals("NA West Coast", regionDisplayName("na_west"))
        assertEquals("NA Rockies", regionDisplayName("na_rockies"))
        assertEquals("NA East Coast", regionDisplayName("na_east"))
        assertEquals("European Alps", regionDisplayName("alps"))
        assertEquals("Scandinavia", regionDisplayName("scandinavia"))
        assertEquals("Japan", regionDisplayName("japan"))
        assertEquals("Oceania", regionDisplayName("oceania"))
        assertEquals("South America", regionDisplayName("south_america"))
    }

    @Test
    fun `asia and eastern europe region display names`() {
        assertEquals("Asia", regionDisplayName("asia"))
        assertEquals("Eastern Europe", regionDisplayName("eastern_europe"))
    }

    @Test
    fun `compound region key with US state`() {
        assertEquals("NA West Coast (California)", regionDisplayName("na_west_CA"))
        assertEquals("NA Rockies (Colorado)", regionDisplayName("na_rockies_CO"))
        assertEquals("NA East Coast (Vermont)", regionDisplayName("na_east_VT"))
    }

    @Test
    fun `compound region key with Canadian province`() {
        assertEquals("NA West Coast (British Columbia)", regionDisplayName("na_west_BC"))
        assertEquals("NA Rockies (Alberta)", regionDisplayName("na_rockies_AB"))
    }

    @Test
    fun `compound region key for non-NA returns base name`() {
        assertEquals("European Alps", regionDisplayName("alps_FR"))
        assertEquals("European Alps", regionDisplayName("alps_CH"))
    }

    @Test
    fun `unknown region capitalizes first letter`() {
        assertEquals("Custom_region", regionDisplayName("custom_region"))
    }

    // =========================================================================
    // Region Inference
    // =========================================================================

    @Test
    fun `japan country maps to japan region`() {
        assertEquals("japan", inferRegion("JP", ""))
    }

    @Test
    fun `australia maps to oceania`() {
        assertEquals("oceania", inferRegion("AU", ""))
    }

    @Test
    fun `new zealand maps to oceania`() {
        assertEquals("oceania", inferRegion("NZ", ""))
    }

    @Test
    fun `chile maps to south america`() {
        assertEquals("south_america", inferRegion("CL", ""))
    }

    @Test
    fun `argentina maps to south america`() {
        assertEquals("south_america", inferRegion("AR", ""))
    }

    @Test
    fun `norway maps to scandinavia`() {
        assertEquals("scandinavia", inferRegion("NO", ""))
    }

    @Test
    fun `sweden maps to scandinavia`() {
        assertEquals("scandinavia", inferRegion("SE", ""))
    }

    @Test
    fun `france maps to alps`() {
        assertEquals("alps", inferRegion("FR", ""))
    }

    @Test
    fun `switzerland maps to alps`() {
        assertEquals("alps", inferRegion("CH", ""))
    }

    @Test
    fun `austria maps to alps`() {
        assertEquals("alps", inferRegion("AT", ""))
    }

    @Test
    fun `italy maps to alps`() {
        assertEquals("alps", inferRegion("IT", ""))
    }

    @Test
    fun `US California maps to na_west`() {
        assertEquals("na_west", inferRegion("US", "CA"))
    }

    @Test
    fun `US Colorado maps to na_rockies`() {
        assertEquals("na_rockies", inferRegion("US", "CO"))
    }

    @Test
    fun `US Vermont maps to na_east`() {
        assertEquals("na_east", inferRegion("US", "VT"))
    }

    @Test
    fun `Canada BC maps to na_west`() {
        assertEquals("na_west", inferRegion("CA", "BC"))
    }

    @Test
    fun `Canada Alberta maps to na_rockies`() {
        assertEquals("na_rockies", inferRegion("CA", "AB"))
    }

    @Test
    fun `Canada Quebec maps to na_east`() {
        assertEquals("na_east", inferRegion("CA", "QC"))
    }

    @Test
    fun `korea maps to asia`() {
        assertEquals("asia", inferRegion("KR", ""))
    }

    @Test
    fun `china maps to asia`() {
        assertEquals("asia", inferRegion("CN", ""))
    }

    @Test
    fun `poland maps to eastern europe`() {
        assertEquals("eastern_europe", inferRegion("PL", ""))
    }

    @Test
    fun `czech republic maps to eastern europe`() {
        assertEquals("eastern_europe", inferRegion("CZ", ""))
    }

    @Test
    fun `slovakia maps to eastern europe`() {
        assertEquals("eastern_europe", inferRegion("SK", ""))
    }

    @Test
    fun `romania maps to eastern europe`() {
        assertEquals("eastern_europe", inferRegion("RO", ""))
    }

    @Test
    fun `bulgaria maps to eastern europe`() {
        assertEquals("eastern_europe", inferRegion("BG", ""))
    }

    @Test
    fun `unknown country defaults to alps`() {
        assertEquals("alps", inferRegion("XX", ""))
    }
}
