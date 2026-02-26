import { Settings, User, LogOut, Thermometer, Snowflake, Info } from 'lucide-react'
import { useAuth } from '../auth/useAuth'
import { useUnits, type TempUnit, type SnowUnit } from '../hooks/useUnits'

export function SettingsPage() {
  const { isAuthenticated, userId, displayName, authProvider, loginAsGuest, logout, isLoading } =
    useAuth()
  const { tempUnit, snowUnit, setTempUnit, setSnowUnit } = useUnits()

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-gray-100 flex items-center justify-center">
          <Settings className="w-5 h-5 text-gray-600" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
      </div>

      {/* Unit Preferences */}
      <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Unit Preferences</h2>

        {/* Temperature */}
        <div className="mb-5">
          <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-3">
            <Thermometer className="w-4 h-4 text-orange-400" />
            Temperature
          </label>
          <div className="flex gap-2">
            {([
              { value: 'celsius' as TempUnit, label: 'Celsius (\u00B0C)' },
              { value: 'fahrenheit' as TempUnit, label: 'Fahrenheit (\u00B0F)' },
            ]).map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setTempUnit(value)}
                className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium border transition-colors ${
                  tempUnit === value
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Snow measurement */}
        <div>
          <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-3">
            <Snowflake className="w-4 h-4 text-blue-400" />
            Snow Measurement
          </label>
          <div className="flex gap-2">
            {([
              { value: 'cm' as SnowUnit, label: 'Centimeters (cm)' },
              { value: 'inches' as SnowUnit, label: 'Inches (")' },
            ]).map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setSnowUnit(value)}
                className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium border transition-colors ${
                  snowUnit === value
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Account */}
      <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Account</h2>

        {isAuthenticated ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-50">
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                <User className="w-5 h-5 text-blue-600" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-900">
                  {displayName || 'Guest User'}
                </p>
                <p className="text-xs text-gray-500">
                  {authProvider === 'guest' ? 'Guest Account' : authProvider}
                  {userId && (
                    <span className="ml-2 text-gray-400">ID: {userId.slice(0, 8)}...</span>
                  )}
                </p>
              </div>
            </div>

            <button
              onClick={logout}
              className="flex items-center gap-2 w-full px-4 py-2.5 rounded-lg text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Sign Out
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-gray-500">
              Sign in to submit condition reports and sync your favorites.
            </p>
            <button
              onClick={loginAsGuest}
              disabled={isLoading}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              <User className="w-4 h-4" />
              Sign In as Guest
            </button>
          </div>
        )}
      </section>

      {/* About */}
      <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">About</h2>
        <div className="space-y-2 text-sm text-gray-600">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-gray-400" />
            <span>Powder Chaser Web</span>
          </div>
          <p className="text-gray-400 text-xs pl-6">
            Real-time snow quality tracking for 130+ ski resorts worldwide.
            AI-powered analysis to help you find the best powder conditions.
          </p>
          <p className="text-gray-400 text-xs pl-6">
            Also available on iOS.
          </p>
        </div>
      </section>
    </div>
  )
}
