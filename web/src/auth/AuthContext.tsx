import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../api/client'

interface AuthState {
  isAuthenticated: boolean
  isLoading: boolean
  userId: string | null
  displayName: string | null
  authProvider: string | null
}

interface AuthContextValue extends AuthState {
  loginAsGuest: () => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

const STORAGE_KEYS = {
  accessToken: 'pc_access_token',
  refreshToken: 'pc_refresh_token',
  tokenExpiry: 'pc_token_expiry',
  deviceId: 'pc_device_id',
  userId: 'pc_user_id',
  displayName: 'pc_display_name',
  authProvider: 'pc_auth_provider',
} as const

function getDeviceId(): string {
  let deviceId = localStorage.getItem(STORAGE_KEYS.deviceId)
  if (!deviceId) {
    deviceId = crypto.randomUUID()
    localStorage.setItem(STORAGE_KEYS.deviceId, deviceId)
  }
  return deviceId
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
    userId: null,
    displayName: null,
    authProvider: null,
  })

  const setAuthenticated = useCallback(
    (userId: string, displayName: string | null, authProvider: string) => {
      setState({
        isAuthenticated: true,
        isLoading: false,
        userId,
        displayName,
        authProvider,
      })
      localStorage.setItem(STORAGE_KEYS.userId, userId)
      if (displayName) localStorage.setItem(STORAGE_KEYS.displayName, displayName)
      localStorage.setItem(STORAGE_KEYS.authProvider, authProvider)
    },
    [],
  )

  const clearAuth = useCallback(() => {
    api.setToken(null)
    localStorage.removeItem(STORAGE_KEYS.accessToken)
    localStorage.removeItem(STORAGE_KEYS.refreshToken)
    localStorage.removeItem(STORAGE_KEYS.tokenExpiry)
    localStorage.removeItem(STORAGE_KEYS.userId)
    localStorage.removeItem(STORAGE_KEYS.displayName)
    localStorage.removeItem(STORAGE_KEYS.authProvider)
    setState({
      isAuthenticated: false,
      isLoading: false,
      userId: null,
      displayName: null,
      authProvider: null,
    })
  }, [])

  // Try to restore session on mount
  useEffect(() => {
    const restoreSession = async () => {
      const accessToken = localStorage.getItem(STORAGE_KEYS.accessToken)
      const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken)
      const expiry = localStorage.getItem(STORAGE_KEYS.tokenExpiry)

      if (!accessToken || !refreshToken) {
        setState((prev) => ({ ...prev, isLoading: false }))
        return
      }

      // Check if token is expired or will expire in the next 60 seconds
      const expiryTime = expiry ? parseInt(expiry, 10) : 0
      const isExpired = Date.now() > expiryTime - 60000

      if (isExpired) {
        try {
          const tokens = await api.refreshToken(refreshToken)
          api.setToken(tokens.access_token)
          localStorage.setItem(STORAGE_KEYS.accessToken, tokens.access_token)
          localStorage.setItem(STORAGE_KEYS.refreshToken, tokens.refresh_token)
          localStorage.setItem(
            STORAGE_KEYS.tokenExpiry,
            String(Date.now() + tokens.expires_in * 1000),
          )

          const me = await api.getMe()
          setAuthenticated(me.user_id, me.display_name, me.auth_provider)
        } catch {
          clearAuth()
        }
      } else {
        api.setToken(accessToken)
        const userId = localStorage.getItem(STORAGE_KEYS.userId)
        const displayName = localStorage.getItem(STORAGE_KEYS.displayName)
        const authProvider = localStorage.getItem(STORAGE_KEYS.authProvider)
        if (userId && authProvider) {
          setAuthenticated(userId, displayName, authProvider)
        } else {
          try {
            const me = await api.getMe()
            setAuthenticated(me.user_id, me.display_name, me.auth_provider)
          } catch {
            clearAuth()
          }
        }
      }
    }

    restoreSession()
  }, [setAuthenticated, clearAuth])

  const loginAsGuest = useCallback(async () => {
    const deviceId = getDeviceId()
    const tokens = await api.guestAuth(deviceId)
    api.setToken(tokens.access_token)
    localStorage.setItem(STORAGE_KEYS.accessToken, tokens.access_token)
    localStorage.setItem(STORAGE_KEYS.refreshToken, tokens.refresh_token)
    localStorage.setItem(
      STORAGE_KEYS.tokenExpiry,
      String(Date.now() + tokens.expires_in * 1000),
    )

    const me = await api.getMe()
    setAuthenticated(me.user_id, me.display_name, me.auth_provider)
  }, [setAuthenticated])

  const logout = useCallback(() => {
    clearAuth()
  }, [clearAuth])

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      loginAsGuest,
      logout,
    }),
    [state, loginAsGuest, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
