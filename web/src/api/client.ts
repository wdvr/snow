import type {
  Resort,
  WeatherCondition,
  SnowQualitySummary,
  TimelineResponse,
  HistoryResponse,
  Region,
  ChatResponse,
  ChatMessage,
  ConversationSummary,
  AuthTokens,
  ConditionReport,
  Recommendation,
} from './types'

const API_BASE = import.meta.env.VITE_API_URL || 'https://api.powderchaserapp.com'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

class ApiClient {
  private accessToken: string | null = null

  setToken(token: string | null) {
    this.accessToken = token
  }

  async fetch<T>(path: string, options?: RequestInit): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`
    }
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...headers, ...options?.headers },
    })
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }))
      throw new ApiError(res.status, error.detail || 'Request failed')
    }
    return res.json()
  }

  // --- Resorts ---

  async getResorts(params?: { region?: string; country?: string }): Promise<Resort[]> {
    const searchParams = new URLSearchParams()
    if (params?.region) searchParams.set('region', params.region)
    if (params?.country) searchParams.set('country', params.country)
    const qs = searchParams.toString()
    const data = await this.fetch<{ resorts: Resort[] }>(`/api/v1/resorts${qs ? `?${qs}` : ''}`)
    return data.resorts
  }

  getResort(id: string): Promise<Resort> {
    return this.fetch<Resort>(`/api/v1/resorts/${id}`)
  }

  async getResortConditions(id: string): Promise<WeatherCondition[]> {
    const data = await this.fetch<{ conditions: WeatherCondition[] }>(`/api/v1/resorts/${id}/conditions`)
    return data.conditions
  }

  async getSnowQualityBatch(ids: string[]): Promise<Record<string, SnowQualitySummary>> {
    const data = await this.fetch<{ results: Record<string, SnowQualitySummary> }>(
      `/api/v1/snow-quality/batch?resort_ids=${ids.join(',')}`,
    )
    return data.results
  }

  getResortSnowQuality(id: string): Promise<Record<string, unknown>> {
    return this.fetch<Record<string, unknown>>(`/api/v1/resorts/${id}/snow-quality`)
  }

  getResortTimeline(id: string): Promise<TimelineResponse> {
    return this.fetch<TimelineResponse>(`/api/v1/resorts/${id}/timeline`)
  }

  getResortHistory(id: string, days?: number): Promise<HistoryResponse> {
    const qs = days ? `?days=${days}` : ''
    return this.fetch<HistoryResponse>(`/api/v1/resorts/${id}/history${qs}`)
  }

  async getRegions(): Promise<Region[]> {
    const data = await this.fetch<{ regions: Region[] }>('/api/v1/regions')
    return data.regions
  }

  async getBestConditions(limit?: number): Promise<Recommendation[]> {
    const qs = limit ? `?limit=${limit}` : ''
    const data = await this.fetch<{ recommendations: Recommendation[] }>(`/api/v1/recommendations/best${qs}`)
    return data.recommendations
  }

  async getConditionReports(resortId: string): Promise<ConditionReport[]> {
    const data = await this.fetch<{ reports: ConditionReport[] }>(`/api/v1/resorts/${resortId}/condition-reports`)
    return data.reports
  }

  getNearbyResorts(lat: number, lon: number, radius?: number, limit?: number): Promise<{ resorts: Array<{ resort: Resort; distance_km: number }>; count: number }> {
    const params = new URLSearchParams({ lat: String(lat), lon: String(lon) })
    if (radius) params.set('radius', String(radius))
    if (limit) params.set('limit', String(limit))
    return this.fetch(`/api/v1/resorts/nearby?${params}`)
  }

  // --- Chat ---

  sendChatMessage(message: string, conversationId?: string): Promise<ChatResponse> {
    return this.fetch<ChatResponse>('/api/v1/chat', {
      method: 'POST',
      body: JSON.stringify({
        message,
        conversation_id: conversationId || null,
      }),
    })
  }

  async getConversations(): Promise<ConversationSummary[]> {
    const data = await this.fetch<{ conversations: ConversationSummary[] }>('/api/v1/chat/conversations')
    return data.conversations
  }

  async getConversation(id: string): Promise<ChatMessage[]> {
    const data = await this.fetch<{ messages: ChatMessage[] }>(`/api/v1/chat/conversations/${id}`)
    return data.messages
  }

  deleteConversation(id: string): Promise<void> {
    return this.fetch<void>(`/api/v1/chat/conversations/${id}`, {
      method: 'DELETE',
    })
  }

  // --- Auth ---

  guestAuth(deviceId: string): Promise<AuthTokens> {
    return this.fetch<AuthTokens>('/api/v1/auth/guest', {
      method: 'POST',
      body: JSON.stringify({ device_id: deviceId }),
    })
  }

  refreshToken(refreshToken: string): Promise<AuthTokens> {
    return this.fetch<AuthTokens>('/api/v1/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
  }

  getMe(): Promise<{ user_id: string; auth_provider: string; display_name: string | null }> {
    return this.fetch('/api/v1/auth/me')
  }
}

export const api = new ApiClient()
