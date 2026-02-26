// --- Enums ---

export type SnowQuality =
  | 'champagne_powder'
  | 'powder_day'
  | 'excellent'
  | 'great'
  | 'good'
  | 'decent'
  | 'mediocre'
  | 'fair'
  | 'poor'
  | 'slushy'
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
  logo_url: string | null
  trail_map_url: string | null
  webcam_url: string | null
  green_runs_pct: number | null
  blue_runs_pct: number | null
  black_runs_pct: number | null
  weather_sources: string[]
  created_at: string | null
  updated_at: string | null
  epic_pass: string | null
  ikon_pass: string | null
  indy_pass: string | null
}

// --- Weather / Conditions ---

export interface SourceDetail {
  snowfall_24h_cm: number | null
  reason: string
  status: 'included' | 'outlier' | 'no_data' | 'consensus' | string
}

export interface SourceDetails {
  sources: Record<string, SourceDetail>
  consensus_value_cm: number | null
  source_count: number
  merge_method: string
}

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
  wind_gust_kmh: number | null
  max_wind_gust_24h_kmh: number | null
  max_wind_gust_24h: number | null
  visibility_m: number | null
  min_visibility_24h_m: number | null
  weather_description: string | null
  snow_quality: SnowQuality
  quality_score: number | null
  confidence_level: string | null
  fresh_snow_cm: number
  data_source: string
  source_confidence: string | null
  source_details: SourceDetails | null
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
  wind_gust_kmh: number | null
  visibility_m: number | null
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
  snowfall_24h_cm: number
  snow_depth_cm: number | null
  temp_min_c: number | null
  temp_max_c: number | null
  snow_quality: string | null
  quality_score: number | null
}

export interface SeasonSummary {
  total_snowfall_cm: number
  snow_days: number
  avg_quality_score: number | null
  best_day: HistoryDay | null
  days_tracked: number
}

export interface HistoryResponse {
  resort_id: string
  history: HistoryDay[]
  season_summary: SeasonSummary
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
