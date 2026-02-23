import {
  Area,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ComposedChart,
  Line,
} from 'recharts'
import type { TimelinePoint, HistoryDay } from '../../api/types'

interface ForecastChartProps {
  timeline: TimelinePoint[]
}

export function ForecastChart({ timeline }: ForecastChartProps) {
  if (timeline.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No forecast data available
      </div>
    )
  }

  // Group by date and aggregate to get daily data for a cleaner chart
  const dailyMap = new Map<
    string,
    { date: string; snowfall_cm: number; temp_min: number; temp_max: number; count: number }
  >()

  for (const point of timeline) {
    const existing = dailyMap.get(point.date)
    if (existing) {
      existing.snowfall_cm += point.snowfall_cm
      existing.temp_min = Math.min(existing.temp_min, point.temperature_c)
      existing.temp_max = Math.max(existing.temp_max, point.temperature_c)
      existing.count++
    } else {
      dailyMap.set(point.date, {
        date: point.date,
        snowfall_cm: point.snowfall_cm,
        temp_min: point.temperature_c,
        temp_max: point.temperature_c,
        count: 1,
      })
    }
  }

  const data = Array.from(dailyMap.values()).map((d) => ({
    date: new Date(d.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
    snowfall: Math.round(d.snowfall_cm * 10) / 10,
    tempMin: Math.round(d.temp_min),
    tempMax: Math.round(d.temp_max),
  }))

  return (
    <div className="w-full">
      <h4 className="text-sm font-medium text-gray-500 mb-4">
        7-Day Forecast: Snowfall & Temperature
      </h4>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12, fill: '#6b7280' }}
            tickLine={false}
          />
          <YAxis
            yAxisId="snow"
            orientation="left"
            tick={{ fontSize: 12, fill: '#6b7280' }}
            tickLine={false}
            axisLine={false}
            label={{ value: 'cm', position: 'insideTopLeft', offset: -5, style: { fontSize: 11, fill: '#9ca3af' } }}
          />
          <YAxis
            yAxisId="temp"
            orientation="right"
            tick={{ fontSize: 12, fill: '#6b7280' }}
            tickLine={false}
            axisLine={false}
            label={{ value: '\u00B0C', position: 'insideTopRight', offset: -5, style: { fontSize: 11, fill: '#9ca3af' } }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '0.5rem',
              fontSize: '0.875rem',
            }}
          />
          <Legend wrapperStyle={{ fontSize: '0.75rem' }} />
          <Bar
            yAxisId="snow"
            dataKey="snowfall"
            name="Snowfall (cm)"
            fill="#3b82f6"
            radius={[4, 4, 0, 0]}
            barSize={24}
          />
          <Line
            yAxisId="temp"
            type="monotone"
            dataKey="tempMax"
            name="High (\u00B0C)"
            stroke="#ef4444"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
          <Line
            yAxisId="temp"
            type="monotone"
            dataKey="tempMin"
            name="Low (\u00B0C)"
            stroke="#6366f1"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

interface HistoryChartProps {
  history: HistoryDay[]
}

export function HistoryChart({ history }: HistoryChartProps) {
  if (history.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No history data available
      </div>
    )
  }

  const data = history.map((day) => ({
    date: new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    snowfall: Math.round((day.snowfall_cm ?? 0) * 10) / 10,
    depth: day.snow_depth_cm != null ? Math.round(day.snow_depth_cm) : null,
  }))

  return (
    <div className="w-full">
      <h4 className="text-sm font-medium text-gray-500 mb-4">
        30-Day Snowfall History
      </h4>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12, fill: '#6b7280' }}
            tickLine={false}
            interval={Math.floor(data.length / 8)}
          />
          <YAxis
            yAxisId="snow"
            orientation="left"
            tick={{ fontSize: 12, fill: '#6b7280' }}
            tickLine={false}
            axisLine={false}
            label={{ value: 'cm', position: 'insideTopLeft', offset: -5, style: { fontSize: 11, fill: '#9ca3af' } }}
          />
          <YAxis
            yAxisId="depth"
            orientation="right"
            tick={{ fontSize: 12, fill: '#6b7280' }}
            tickLine={false}
            axisLine={false}
            label={{ value: 'depth cm', position: 'insideTopRight', offset: -5, style: { fontSize: 11, fill: '#9ca3af' } }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'white',
              border: '1px solid #e5e7eb',
              borderRadius: '0.5rem',
              fontSize: '0.875rem',
            }}
          />
          <Legend wrapperStyle={{ fontSize: '0.75rem' }} />
          <Bar
            yAxisId="snow"
            dataKey="snowfall"
            name="Daily Snowfall (cm)"
            fill="#60a5fa"
            radius={[2, 2, 0, 0]}
          />
          <Area
            yAxisId="depth"
            type="monotone"
            dataKey="depth"
            name="Snow Depth (cm)"
            stroke="#a78bfa"
            fill="#a78bfa"
            fillOpacity={0.15}
            strokeWidth={2}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
