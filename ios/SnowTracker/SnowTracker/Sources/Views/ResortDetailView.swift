import SwiftUI

struct ResortDetailView: View {
    let resort: Resort
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @State private var selectedElevation: ElevationLevel = .top
    @State private var showingShareSheet: Bool = false

    private var conditions: [WeatherCondition] {
        snowConditionsManager.conditions[resort.id] ?? []
    }

    private var conditionForSelectedElevation: WeatherCondition? {
        conditions.first { $0.elevationLevel == selectedElevation.rawValue }
    }

    private var shareText: String {
        var text = "🏔️ \(resort.name) Snow Report\n"
        text += "📍 \(resort.displayLocation)\n\n"

        if let condition = conditionForSelectedElevation {
            text += "Current Conditions (\(selectedElevation.displayName)):\n"
            text += "❄️ Snow Quality: \(condition.snowQuality.displayName)\n"
            text += "🌡️ Temperature: \(Int(condition.currentTempCelsius))°C / \(Int(condition.currentTempFahrenheit))°F\n"
            text += "🆕 Fresh Snow: \(String(format: "%.0f", condition.freshSnowCm))cm\n"
            text += "📊 24h Snowfall: \(String(format: "%.1f", condition.snowfall24hCm))cm\n"
        } else {
            text += "No current conditions available.\n"
        }

        text += "\n📱 Tracked with Snow Tracker"
        return text
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Resort header
                resortHeader

                // Elevation picker
                elevationPicker

                // Current conditions
                if let condition = conditionForSelectedElevation {
                    currentConditionsCard(condition)
                    snowDetailsCard(condition)
                    predictionsCard(condition)
                    weatherDetailsCard(condition)
                } else {
                    noDataCard
                }

                // All elevations summary
                allElevationsSummary
            }
            .padding()
        }
        .navigationTitle(resort.name)
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                HStack(spacing: 16) {
                    Button {
                        showingShareSheet = true
                    } label: {
                        Image(systemName: "square.and.arrow.up")
                            .foregroundColor(.blue)
                    }

                    Button {
                        userPreferencesManager.toggleFavorite(resortId: resort.id)
                    } label: {
                        Image(systemName: userPreferencesManager.isFavorite(resortId: resort.id) ? "heart.fill" : "heart")
                            .foregroundColor(userPreferencesManager.isFavorite(resortId: resort.id) ? .red : .gray)
                    }
                }
            }
        }
        .sheet(isPresented: $showingShareSheet) {
            ShareSheet(items: [shareText])
        }
        .refreshable {
            await snowConditionsManager.refreshConditions()
        }
    }

    // MARK: - Resort Header

    private var resortHeader: some View {
        VStack(spacing: 8) {
            HStack {
                VStack(alignment: .leading) {
                    Text(resort.displayLocation)
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    Text(resort.elevationRange)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()

                // Overall snow quality badge
                if let condition = conditions.first {
                    VStack {
                        Image(systemName: condition.snowQuality.icon)
                            .font(.title)
                            .foregroundColor(condition.snowQuality.color)
                        Text(condition.snowQuality.displayName)
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(condition.snowQuality.color)
                    }
                    .padding()
                    .background(
                        RoundedRectangle(cornerRadius: 12)
                            .fill(condition.snowQuality.color.opacity(0.1))
                    )
                }
            }

            if let website = resort.officialWebsite, let url = URL(string: website) {
                Link(destination: url) {
                    Label("Visit Website", systemImage: "safari")
                        .font(.caption)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }

    // MARK: - Elevation Picker

    private var elevationPicker: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Select Elevation")
                .font(.headline)

            Picker("Elevation", selection: $selectedElevation) {
                ForEach(ElevationLevel.allCases, id: \.self) { level in
                    if let point = resort.elevationPoint(for: level) {
                        Text("\(level.displayName) - \(point.formattedFeet)")
                            .tag(level)
                    }
                }
            }
            .pickerStyle(.segmented)
        }
    }

    // MARK: - Current Conditions Card

    private func currentConditionsCard(_ condition: WeatherCondition) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Current Conditions")
                    .font(.headline)

                Spacer()

                Text(condition.formattedTimestamp)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            HStack(spacing: 20) {
                // Temperature
                VStack {
                    Image(systemName: "thermometer")
                        .font(.title2)
                        .foregroundColor(.blue)
                    Text("\(Int(condition.currentTempCelsius))°C")
                        .font(.title2)
                        .fontWeight(.bold)
                    Text("\(Int(condition.currentTempFahrenheit))°F")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity)

                // Snow Quality
                VStack {
                    Image(systemName: condition.snowQuality.icon)
                        .font(.title2)
                        .foregroundColor(condition.snowQuality.color)
                    Text(condition.snowQuality.displayName)
                        .font(.title3)
                        .fontWeight(.bold)
                        .foregroundColor(condition.snowQuality.color)
                    Text(condition.confidenceLevel.displayName)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity)

                // Fresh Snow
                VStack {
                    Image(systemName: "snowflake")
                        .font(.title2)
                        .foregroundColor(.cyan)
                    Text("\(String(format: "%.0f", condition.freshSnowCm))cm")
                        .font(.title2)
                        .fontWeight(.bold)
                    Text("Fresh")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }

    // MARK: - Snow Details Card

    private func snowDetailsCard(_ condition: WeatherCondition) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Snowfall")
                .font(.headline)

            HStack(spacing: 20) {
                snowfallItem(title: "24h", value: condition.snowfall24hCm)
                snowfallItem(title: "48h", value: condition.snowfall48hCm)
                snowfallItem(title: "72h", value: condition.snowfall72hCm)
            }

            Divider()

            // Ice formation info
            HStack {
                VStack(alignment: .leading) {
                    Text("Hours Above Freezing")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("\(String(format: "%.1f", condition.hoursAboveIceThreshold))h")
                        .font(.body)
                        .fontWeight(.medium)
                }

                Spacer()

                VStack(alignment: .trailing) {
                    Text("Max Consecutive Warm")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("\(String(format: "%.1f", condition.maxConsecutiveWarmHours))h")
                        .font(.body)
                        .fontWeight(.medium)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }

    private func snowfallItem(title: String, value: Double) -> some View {
        VStack {
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
            Text("\(String(format: "%.1f", value))cm")
                .font(.title3)
                .fontWeight(.semibold)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Predictions Card

    private func predictionsCard(_ condition: WeatherCondition) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .foregroundColor(.blue)
                Text("Snow Forecast")
                    .font(.headline)
            }

            HStack(spacing: 20) {
                predictionItem(
                    title: "Next 24h",
                    value: condition.predictedSnow24hCm ?? 0.0
                )
                predictionItem(
                    title: "Next 48h",
                    value: condition.predictedSnow48hCm ?? 0.0
                )
                predictionItem(
                    title: "Next 72h",
                    value: condition.predictedSnow72hCm ?? 0.0
                )
            }

            // Prediction insight
            if let predicted24h = condition.predictedSnow24hCm, predicted24h > 10 {
                HStack {
                    Image(systemName: "snowflake.circle.fill")
                        .foregroundColor(.blue)
                    Text("Heavy snowfall expected!")
                        .font(.subheadline)
                        .foregroundColor(.blue)
                        .fontWeight(.medium)
                }
                .padding(.top, 4)
            } else if let predicted24h = condition.predictedSnow24hCm, predicted24h > 5 {
                HStack {
                    Image(systemName: "cloud.snow")
                        .foregroundColor(.secondary)
                    Text("Light snow expected")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.top, 4)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }

    private func predictionItem(title: String, value: Double) -> some View {
        VStack {
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
            Text("\(String(format: "%.1f", value))cm")
                .font(.title3)
                .fontWeight(.semibold)
                .foregroundColor(.blue)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Weather Details Card

    private func weatherDetailsCard(_ condition: WeatherCondition) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Weather Details")
                .font(.headline)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                weatherDetailItem(
                    icon: "thermometer.low",
                    title: "Min Temp",
                    value: "\(Int(condition.minTempCelsius))°C"
                )

                weatherDetailItem(
                    icon: "thermometer.high",
                    title: "Max Temp",
                    value: "\(Int(condition.maxTempCelsius))°C"
                )

                if let humidity = condition.humidityPercent {
                    weatherDetailItem(
                        icon: "humidity",
                        title: "Humidity",
                        value: "\(Int(humidity))%"
                    )
                }

                if let wind = condition.windSpeedKmh {
                    weatherDetailItem(
                        icon: "wind",
                        title: "Wind",
                        value: "\(Int(wind)) km/h"
                    )
                }
            }

            if let description = condition.weatherDescription {
                HStack {
                    Image(systemName: "cloud")
                        .foregroundColor(.secondary)
                    Text(description)
                        .font(.body)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }

    private func weatherDetailItem(icon: String, title: String, value: String) -> some View {
        HStack {
            Image(systemName: icon)
                .foregroundColor(.blue)
                .frame(width: 24)

            VStack(alignment: .leading) {
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text(value)
                    .font(.body)
                    .fontWeight(.medium)
            }

            Spacer()
        }
        .padding(.vertical, 4)
    }

    // MARK: - All Elevations Summary

    private var allElevationsSummary: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("All Elevations")
                .font(.headline)

            ForEach(ElevationLevel.allCases, id: \.self) { level in
                if let point = resort.elevationPoint(for: level),
                   let condition = conditions.first(where: { $0.elevationLevel == level.rawValue }) {
                    HStack {
                        Image(systemName: level.icon)
                            .foregroundColor(.blue)
                            .frame(width: 24)

                        VStack(alignment: .leading) {
                            Text(level.displayName)
                                .font(.body)
                                .fontWeight(.medium)
                            Text(point.formattedFeet)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }

                        Spacer()

                        VStack(alignment: .trailing) {
                            HStack(spacing: 4) {
                                Image(systemName: condition.snowQuality.icon)
                                    .foregroundColor(condition.snowQuality.color)
                                Text(condition.snowQuality.displayName)
                                    .foregroundColor(condition.snowQuality.color)
                            }
                            .font(.subheadline)

                            Text("\(Int(condition.currentTempCelsius))°C")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .padding(.vertical, 8)

                    if level != .base {
                        Divider()
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }

    // MARK: - No Data Card

    private var noDataCard: some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundColor(.orange)

            Text("No Data Available")
                .font(.headline)

            Text("Weather conditions for this elevation are not currently available. Pull to refresh.")
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(radius: 2)
    }
}

// MARK: - Share Sheet

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

#Preview("Resort Detail") {
    NavigationStack {
        ResortDetailView(resort: Resort.sampleResorts[0])
            .environmentObject(SnowConditionsManager())
            .environmentObject(UserPreferencesManager.shared)
    }
}
