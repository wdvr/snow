// --- Enums ---

export type SnowQuality =
  | 'excellent'
  | 'good'
  | 'fair'
  | 'poor'
  | 'bad'
  | 'horrible'
  | 'unknown'

export type ElevationLevel = 'base' | 'mid' | 'top'

export type ConditionType =
  | 'powder'
  | 'packed_powder'
  | 'soft'
  | 'ice'
  | 'crud'
  | 'spring'
  | 'hardpack'
  | 'windblown'

// --- Resort ---

export interface ElevationPoint {
  level: ElevationLevel
  elevation_meters: number
  elevation_feet: number
  latitude: number
  longitude: number
  weather_station_id: string | null
}

export interface Resort {
  resort_id: string
  name: string
  country: string
  region: string
  elevation_points: ElevationPoint[]
  timezone: string
  official_website: string | null
  trail_map_url: string | null
  green_runs_pct: number | null
  blue_runs_pct: number | null
  black_runs_pct: number | null
  weather_sources: string[]
  created_at: string | null
  updated_at: string | null
  epic_pass: string | null
  ikon_pass: string | null
}

// --- Weather / Conditions ---

export interface WeatherCondition {
  resort_id: string
  elevation_level: string
  timestamp: string
  current_temp_celsius: number
  min_temp_celsius: number
  max_temp_celsius: number
  snowfall_24h_cm: number
  snowfall_48h_cm: number
  snowfall_72h_cm: number
  snow_depth_cm: number | null
  predicted_snow_24h_cm: number
  predicted_snow_48h_cm: number
  predicted_snow_72h_cm: number
  hours_above_ice_threshold: number
  max_consecutive_warm_hours: number
  snowfall_after_freeze_cm: number
  hours_since_last_snowfall: number | null
  last_freeze_thaw_hours_ago: number | null
  currently_warming: boolean
  humidity_percent: number | null
  wind_speed_kmh: number | null
  weather_description: string | null
  snow_quality: SnowQuality
  quality_score: number | null
  fresh_snow_cm: number
  data_source: string
}

// --- Snow Quality Batch ---

export interface SnowQualitySummary {
  resort_id: string
  overall_quality: SnowQuality
  snow_score: number | null
  explanation: string | null
  last_updated: string | null
  temperature_c: number | null
  snowfall_fresh_cm: number | null
  snowfall_24h_cm: number | null
  snow_depth_cm: number | null
  predicted_snow_48h_cm: number | null
}

// --- Timeline ---

export interface TimelinePoint {
  date: string
  time_label: string
  hour: number
  timestamp: string
  temperature_c: number
  wind_speed_kmh: number | null
  snowfall_cm: number
  snow_depth_cm: number | null
  snow_quality: string
  quality_score: number | null
  snow_score: number | null
  explanation: string | null
  weather_code: number | null
  weather_description: string | null
  is_forecast: boolean
}

export interface TimelineResponse {
  timeline: TimelinePoint[]
  elevation_level: string
  elevation_meters: number
  resort_id: string
}

// --- History ---

export interface HistoryDay {
  date: string
  snowfall_cm: number
  snow_depth_cm: number | null
  min_temp_c: number | null
  max_temp_c: number | null
  snow_quality: string | null
  quality_score: number | null
}

export interface HistoryResponse {
  resort_id: string
  days: HistoryDay[]
  season_total_cm: number
  season_total_inches: number
}

// --- Regions ---

export interface Region {
  id: string
  name: string
  display_name: string
  resort_count: number
}

// --- Chat ---

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  message_id: string
  created_at: string
}

export interface ChatResponse {
  conversation_id: string
  response: string
  message_id: string
}

export interface ConversationSummary {
  conversation_id: string
  title: string
  last_message_at: string
  message_count: number
}

// --- Auth ---

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface GuestAuthRequest {
  device_id: string
}

export interface UserInfo {
  user_id: string
  auth_provider: string
  display_name: string | null
}

// --- Condition Reports ---

export interface ConditionReport {
  report_id: string
  resort_id: string
  condition_type: ConditionType
  score: number
  comment: string | null
  elevation_level: string | null
  created_at: string
  user_display_name: string | null
}

// --- Recommendations ---

export interface Recommendation {
  resort: Resort
  distance_km: number
  distance_miles: number
  snow_quality: SnowQuality
  snow_score: number | null
  quality_score: number
  fresh_snow_cm: number
  predicted_snow_72h_cm: number
  current_temp_celsius: number
  reason: string
}
