package com.powderchaserapp.android.ui.screens.resortdetail

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AcUnit
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.powderchaserapp.android.data.api.TimelinePoint
import com.powderchaserapp.android.data.api.TimelineResponse
import com.powderchaserapp.android.data.api.WeatherCondition
import com.powderchaserapp.android.ui.theme.SnowColors
import com.powderchaserapp.android.util.UnitConversions
import com.powderchaserapp.android.util.UnitPreferences
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import kotlin.math.roundToInt

/**
 * Daily aggregated snow data for the chart.
 */
private data class DailySnowData(
    val date: String, // yyyy-MM-dd
    val snowfallCm: Double,
    val minTempC: Double,
    val maxTempC: Double,
    val isForecast: Boolean,
) {
    val shortDate: String
        get() = try {
            val parsed = LocalDate.parse(date, DateTimeFormatter.ISO_LOCAL_DATE)
            parsed.format(DateTimeFormatter.ofPattern("MMM d"))
        } catch (_: Exception) {
            date.takeLast(5)
        }

    fun snowfallDisplay(useMetric: Boolean): Double =
        if (useMetric) snowfallCm else UnitConversions.cmToInches(snowfallCm)
}

/**
 * Aggregate timeline points into daily totals.
 */
private fun aggregateDailyData(timeline: List<TimelinePoint>): List<DailySnowData> {
    data class Accumulator(
        var snowfall: Double = 0.0,
        var minTemp: Double = Double.MAX_VALUE,
        var maxTemp: Double = Double.MIN_VALUE,
        var isForecast: Boolean = false,
    )

    val byDate = linkedMapOf<String, Accumulator>()
    for (point in timeline) {
        val acc = byDate.getOrPut(point.date) { Accumulator() }
        acc.snowfall += point.snowfallCm
        acc.minTemp = minOf(acc.minTemp, point.temperatureC)
        acc.maxTemp = maxOf(acc.maxTemp, point.temperatureC)
        if (point.isForecast) acc.isForecast = true
    }

    return byDate.entries.sortedBy { it.key }.map { (date, acc) ->
        DailySnowData(
            date = date,
            snowfallCm = acc.snowfall,
            minTempC = if (acc.minTemp == Double.MAX_VALUE) 0.0 else acc.minTemp,
            maxTempC = if (acc.maxTemp == Double.MIN_VALUE) 0.0 else acc.maxTemp,
            isForecast = acc.isForecast,
        )
    }
}

/**
 * Fresh snow bar chart showing daily snowfall over the 7-day timeline period.
 * Uses Compose Canvas for rendering -- no external chart library needed.
 */
@Composable
fun FreshSnowChart(
    timeline: TimelineResponse,
    condition: WeatherCondition?,
    units: UnitPreferences,
) {
    val dailyData = remember(timeline) { aggregateDailyData(timeline.timeline) }
    if (dailyData.isEmpty()) return

    val useMetric = units.useMetricSnow
    val snowUnit = if (useMetric) "cm" else "in"
    val freshTotal = condition?.let {
        it.snowfallAfterFreezeCm ?: it.freshSnowCm.toDouble()
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 4.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Header
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    Icons.Default.AcUnit,
                    contentDescription = null,
                    tint = SnowColors.IceBlue,
                    modifier = Modifier.size(20.dp),
                )
                Spacer(modifier = Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        "Fresh Powder",
                        style = MaterialTheme.typography.titleMedium,
                    )
                    if (freshTotal != null && freshTotal > 0) {
                        Text(
                            "${UnitConversions.formatSnow(freshTotal, useMetric)} since last thaw",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Bar chart
            val textMeasurer = rememberTextMeasurer()
            val barColorActual = SnowColors.IceBlue.copy(alpha = 0.8f)
            val barColorForecast = SnowColors.IceBlue.copy(alpha = 0.4f)
            val labelColor = MaterialTheme.colorScheme.onSurfaceVariant
            val valueColor = MaterialTheme.colorScheme.onSurface

            Canvas(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(180.dp),
            ) {
                drawSnowBarChart(
                    dailyData = dailyData,
                    useMetric = useMetric,
                    textMeasurer = textMeasurer,
                    barColorActual = barColorActual,
                    barColorForecast = barColorForecast,
                    labelColor = labelColor,
                    valueColor = valueColor,
                )
            }

            // Legend
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                horizontalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                LegendItem(
                    color = SnowColors.IceBlue.copy(alpha = 0.8f),
                    label = "Snowfall ($snowUnit)",
                )
                if (dailyData.any { it.isForecast }) {
                    LegendItem(
                        color = SnowColors.IceBlue.copy(alpha = 0.4f),
                        label = "Forecast",
                    )
                }
            }
        }
    }
}

@Composable
private fun LegendItem(color: Color, label: String) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Canvas(modifier = Modifier.size(10.dp)) {
            drawRoundRect(
                color = color,
                cornerRadius = CornerRadius(2f, 2f),
            )
        }
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

private fun DrawScope.drawSnowBarChart(
    dailyData: List<DailySnowData>,
    useMetric: Boolean,
    textMeasurer: TextMeasurer,
    barColorActual: Color,
    barColorForecast: Color,
    labelColor: Color,
    valueColor: Color,
) {
    val count = dailyData.size
    if (count == 0) return

    val chartWidth = size.width
    val chartHeight = size.height

    // Reserve space for labels at bottom and values at top
    val bottomLabelHeight = 24f
    val topValueHeight = 20f
    val barAreaTop = topValueHeight
    val barAreaBottom = chartHeight - bottomLabelHeight
    val barAreaHeight = barAreaBottom - barAreaTop

    // Calculate bar dimensions
    val barSpacing = 8f
    val totalSpacing = barSpacing * (count + 1)
    val barWidth = ((chartWidth - totalSpacing) / count).coerceAtLeast(12f)

    // Find max snowfall for scaling
    val maxSnow = dailyData.maxOf { it.snowfallDisplay(useMetric) }.coerceAtLeast(1.0)

    val dateLabelStyle = TextStyle(
        fontSize = 10.sp,
        color = labelColor,
        textAlign = TextAlign.Center,
    )
    val valueLabelStyle = TextStyle(
        fontSize = 9.sp,
        color = valueColor,
        fontWeight = FontWeight.Medium,
        textAlign = TextAlign.Center,
    )

    dailyData.forEachIndexed { index, day ->
        val x = barSpacing + index * (barWidth + barSpacing)
        val snowVal = day.snowfallDisplay(useMetric)
        val barHeight = if (maxSnow > 0) {
            ((snowVal / maxSnow) * barAreaHeight * 0.85).toFloat().coerceAtLeast(0f)
        } else {
            0f
        }

        val barColor = if (day.isForecast) barColorForecast else barColorActual

        // Draw bar
        if (barHeight > 0) {
            val barTop = barAreaBottom - barHeight
            drawRoundRect(
                color = barColor,
                topLeft = Offset(x, barTop),
                size = Size(barWidth, barHeight),
                cornerRadius = CornerRadius(4f, 4f),
            )

            // Draw value label above bar
            if (snowVal >= 0.5) {
                val valueText = if (snowVal >= 10) {
                    "${snowVal.roundToInt()}"
                } else {
                    String.format("%.1f", snowVal)
                }
                val valueLayout = textMeasurer.measure(valueText, valueLabelStyle)
                drawText(
                    textLayoutResult = valueLayout,
                    topLeft = Offset(
                        x + (barWidth - valueLayout.size.width) / 2f,
                        barTop - valueLayout.size.height - 2f,
                    ),
                )
            }
        }

        // Draw date label at bottom
        val dateText = day.shortDate
        val dateLayout = textMeasurer.measure(dateText, dateLabelStyle)
        drawText(
            textLayoutResult = dateLayout,
            topLeft = Offset(
                x + (barWidth - dateLayout.size.width) / 2f,
                barAreaBottom + 4f,
            ),
        )
    }
}
