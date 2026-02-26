import {
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  BarChart,
} from 'recharts'
import type { TimelinePoint } from '../../api/types'

interface FreshSnowChartProps {
  timeline: TimelinePoint[]
}

export function FreshSnowChart({ timeline }: FreshSnowChartProps) {
  if (timeline.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No snowfall data available
      </div>
    )
  }

  // Group by date and aggregate snowfall
  const dailyMap = new Map<string, { date: string; snowfall_cm: number }>()

  for (const point of timeline) {
    const existing = dailyMap.get(point.date)
    if (existing) {
      existing.snowfall_cm += point.snowfall_cm
    } else {
      dailyMap.set(point.date, {
        date: point.date,
        snowfall_cm: point.snowfall_cm,
      })
    }
  }

  const data = Array.from(dailyMap.values())
    .map((d) => ({
      date: new Date(d.date).toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
      }),
      snowfall: Math.round(d.snowfall_cm * 10) / 10,
    }))

  const hasSnow = data.some((d) => d.snowfall > 0)
  if (!hasSnow) {
    return (
      <div className="text-center py-8 text-gray-500">
        No snowfall recorded in this period
      </div>
    )
  }

  return (
    <div className="w-full">
      <h4 className="text-sm font-medium text-gray-500 mb-4">
        7-Day Snowfall
      </h4>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12, fill: '#6b7280' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 12, fill: '#6b7280' }}
            tickLine={false}
            axisLine={false}
            label={{
              value: 'cm',
              position: 'insideTopLeft',
              offset: -5,
              style: { fontSize: 11, fill: '#9ca3af' },
            }}
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
            dataKey="snowfall"
            name="Snowfall (cm)"
            fill="#60a5fa"
            radius={[4, 4, 0, 0]}
            barSize={24}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
