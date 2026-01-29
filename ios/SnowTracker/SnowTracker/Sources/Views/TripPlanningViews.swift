import SwiftUI

// MARK: - Trip Planning Manager

@MainActor
class TripPlanningManager: ObservableObject {
    @Published var trips: [Trip] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let apiClient = APIClient.shared

    var upcomingTrips: [Trip] {
        trips.filter { $0.tripStatus == .planned || $0.tripStatus == .active }
            .sorted { ($0.daysUntilTrip ?? Int.max) < ($1.daysUntilTrip ?? Int.max) }
    }

    var pastTrips: [Trip] {
        trips.filter { $0.tripStatus == .completed || $0.tripStatus == .cancelled }
            .sorted { $0.startDate > $1.startDate }
    }

    func loadTrips() async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await apiClient.getTrips()
            trips = response.trips
        } catch {
            errorMessage = error.localizedDescription
            print("Error loading trips: \(error)")
        }

        isLoading = false
    }

    func createTrip(resortId: String, startDate: Date, endDate: Date, notes: String?, partySize: Int) async throws -> Trip {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"

        let request = TripCreateRequest(
            resortId: resortId,
            startDate: formatter.string(from: startDate),
            endDate: formatter.string(from: endDate),
            notes: notes,
            partySize: partySize,
            alertPreferences: [
                "powder_alerts": true,
                "warm_spell_warnings": true,
                "condition_updates": true,
                "trip_reminders": true
            ]
        )

        let trip = try await apiClient.createTrip(request)
        trips.append(trip)
        return trip
    }

    func updateTrip(_ trip: Trip, startDate: Date?, endDate: Date?, notes: String?, partySize: Int?, status: TripStatus?) async throws -> Trip {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"

        let request = TripUpdateRequest(
            startDate: startDate.map { formatter.string(from: $0) },
            endDate: endDate.map { formatter.string(from: $0) },
            notes: notes,
            partySize: partySize,
            status: status?.rawValue,
            alertPreferences: nil
        )

        let updatedTrip = try await apiClient.updateTrip(tripId: trip.tripId, update: request)

        if let index = trips.firstIndex(where: { $0.tripId == trip.tripId }) {
            trips[index] = updatedTrip
        }

        return updatedTrip
    }

    func deleteTrip(_ trip: Trip) async throws {
        try await apiClient.deleteTrip(tripId: trip.tripId)
        trips.removeAll { $0.tripId == trip.tripId }
    }

    func refreshTripConditions(_ trip: Trip) async throws -> Trip {
        let updatedTrip = try await apiClient.refreshTripConditions(tripId: trip.tripId)

        if let index = trips.firstIndex(where: { $0.tripId == trip.tripId }) {
            trips[index] = updatedTrip
        }

        return updatedTrip
    }

    func markAlertsRead(_ trip: Trip) async throws -> Trip {
        let updatedTrip = try await apiClient.markAlertsRead(tripId: trip.tripId)

        if let index = trips.firstIndex(where: { $0.tripId == trip.tripId }) {
            trips[index] = updatedTrip
        }

        return updatedTrip
    }
}

// MARK: - Trips List View

struct TripsListView: View {
    @StateObject private var tripManager = TripPlanningManager()
    @State private var showingCreateTrip = false
    @State private var selectedResort: Resort?

    var body: some View {
        NavigationStack {
            Group {
                if tripManager.isLoading && tripManager.trips.isEmpty {
                    ProgressView("Loading trips...")
                } else if tripManager.trips.isEmpty {
                    emptyStateView
                } else {
                    tripsList
                }
            }
            .navigationTitle("My Trips")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button(action: { showingCreateTrip = true }) {
                        Image(systemName: "plus")
                    }
                }
            }
            .refreshable {
                await tripManager.loadTrips()
            }
            .sheet(isPresented: $showingCreateTrip) {
                CreateTripView(tripManager: tripManager)
            }
            .task {
                await tripManager.loadTrips()
            }
        }
    }

    private var emptyStateView: some View {
        ContentUnavailableView {
            Label("No Trips Planned", systemImage: "calendar.badge.plus")
        } description: {
            Text("Plan your next ski trip to track conditions and get alerts.")
        } actions: {
            Button("Plan a Trip") {
                showingCreateTrip = true
            }
            .buttonStyle(.borderedProminent)
        }
    }

    private var tripsList: some View {
        List {
            if !tripManager.upcomingTrips.isEmpty {
                Section("Upcoming") {
                    ForEach(tripManager.upcomingTrips) { trip in
                        NavigationLink(destination: TripDetailView(trip: trip, tripManager: tripManager)) {
                            TripRowView(trip: trip)
                        }
                    }
                    .onDelete { indexSet in
                        Task {
                            for index in indexSet {
                                let trip = tripManager.upcomingTrips[index]
                                try? await tripManager.deleteTrip(trip)
                            }
                        }
                    }
                }
            }

            if !tripManager.pastTrips.isEmpty {
                Section("Past") {
                    ForEach(tripManager.pastTrips) { trip in
                        NavigationLink(destination: TripDetailView(trip: trip, tripManager: tripManager)) {
                            TripRowView(trip: trip)
                        }
                    }
                }
            }
        }
    }
}

// MARK: - Trip Row View

struct TripRowView: View {
    let trip: Trip

    private var statusColor: Color {
        switch trip.tripStatus {
        case .planned: return .blue
        case .active: return .green
        case .completed: return .gray
        case .cancelled: return .red
        }
    }

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(trip.resortName)
                    .font(.headline)

                HStack {
                    Image(systemName: "calendar")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(formatDateRange())
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                if let days = trip.daysUntilTrip, days >= 0 {
                    Text(daysUntilText(days))
                        .font(.caption)
                        .foregroundColor(.blue)
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 4) {
                // Status badge
                Text(trip.tripStatus.rawValue.capitalized)
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(statusColor.opacity(0.2))
                    .foregroundColor(statusColor)
                    .cornerRadius(4)

                // Alert badge
                if trip.unreadAlertCount > 0 {
                    HStack(spacing: 2) {
                        Image(systemName: "bell.fill")
                            .font(.caption2)
                        Text("\(trip.unreadAlertCount)")
                            .font(.caption2)
                    }
                    .foregroundColor(.orange)
                }
            }
        }
        .padding(.vertical, 4)
    }

    private func formatDateRange() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"

        if let start = trip.startDateFormatted, let end = trip.endDateFormatted {
            if start == end {
                return formatter.string(from: start)
            }
            return "\(formatter.string(from: start)) - \(formatter.string(from: end))"
        }
        return "\(trip.startDate) - \(trip.endDate)"
    }

    private func daysUntilText(_ days: Int) -> String {
        if days == 0 {
            return "Today!"
        } else if days == 1 {
            return "Tomorrow"
        } else {
            return "In \(days) days"
        }
    }
}

// MARK: - Trip Detail View

struct TripDetailView: View {
    let trip: Trip
    @ObservedObject var tripManager: TripPlanningManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

    @State private var isRefreshing = false
    @State private var showingEditSheet = false
    @State private var showingDeleteAlert = false

    @Environment(\.dismiss) private var dismiss

    var useMetric: Bool {
        userPreferencesManager.preferredUnits.distance == .metric
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Header Card
                headerCard

                // Conditions Card
                if let conditions = trip.latestConditions {
                    conditionsCard(conditions)
                }

                // Alerts Section
                if !trip.alerts.isEmpty {
                    alertsSection
                }

                // Details Section
                detailsSection

                // Actions
                actionsSection
            }
            .padding()
        }
        .navigationTitle(trip.resortName)
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button(action: { showingEditSheet = true }) {
                        Label("Edit Trip", systemImage: "pencil")
                    }
                    Button(role: .destructive, action: { showingDeleteAlert = true }) {
                        Label("Delete Trip", systemImage: "trash")
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
        .refreshable {
            await refreshConditions()
        }
        .sheet(isPresented: $showingEditSheet) {
            EditTripView(trip: trip, tripManager: tripManager)
        }
        .alert("Delete Trip", isPresented: $showingDeleteAlert) {
            Button("Cancel", role: .cancel) { }
            Button("Delete", role: .destructive) {
                Task {
                    try? await tripManager.deleteTrip(trip)
                    dismiss()
                }
            }
        } message: {
            Text("Are you sure you want to delete this trip?")
        }
    }

    private var headerCard: some View {
        VStack(spacing: 12) {
            // Date range
            HStack {
                Image(systemName: "calendar")
                    .foregroundColor(.blue)
                Text(formatDateRange())
                    .font(.title3)
                    .fontWeight(.semibold)
            }

            // Days until / duration
            HStack(spacing: 20) {
                if let days = trip.daysUntilTrip, days >= 0 {
                    VStack {
                        Text("\(days)")
                            .font(.title)
                            .fontWeight(.bold)
                            .foregroundColor(.blue)
                        Text("days until")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                VStack {
                    Text("\(trip.tripDurationDays)")
                        .font(.title)
                        .fontWeight(.bold)
                    Text("day\(trip.tripDurationDays == 1 ? "" : "s")")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                VStack {
                    Text("\(trip.partySize)")
                        .font(.title)
                        .fontWeight(.bold)
                    Text("people")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }

    private func conditionsCard(_ conditions: TripConditionSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Current Conditions")
                    .font(.headline)
                Spacer()
                QualityBadge(quality: conditions.quality)
            }

            HStack(spacing: 20) {
                VStack {
                    Image(systemName: "snowflake")
                        .foregroundColor(.cyan)
                    Text(formatSnow(conditions.freshSnowCm))
                        .font(.subheadline)
                        .fontWeight(.semibold)
                    Text("Fresh")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }

                VStack {
                    Image(systemName: "cloud.snow")
                        .foregroundColor(.purple)
                    Text("+\(formatSnow(conditions.predictedSnowCm))")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                    Text("Expected")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }

                if let temp = conditions.temperatureCelsius {
                    VStack {
                        Image(systemName: "thermometer.medium")
                            .foregroundColor(temp < 0 ? .blue : .orange)
                        Text(formatTemp(temp))
                            .font(.subheadline)
                            .fontWeight(.semibold)
                        Text("Temp")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
            }
            .frame(maxWidth: .infinity)

            Button(action: { Task { await refreshConditions() } }) {
                HStack {
                    if isRefreshing {
                        ProgressView()
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "arrow.clockwise")
                    }
                    Text("Refresh Conditions")
                }
                .font(.subheadline)
            }
            .buttonStyle(.bordered)
            .disabled(isRefreshing)
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }

    private var alertsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Alerts")
                    .font(.headline)
                if trip.unreadAlertCount > 0 {
                    Text("\(trip.unreadAlertCount) new")
                        .font(.caption)
                        .foregroundColor(.orange)
                }
                Spacer()
                Button("Mark all read") {
                    Task { try? await tripManager.markAlertsRead(trip) }
                }
                .font(.caption)
                .disabled(trip.unreadAlertCount == 0)
            }

            ForEach(trip.alerts.prefix(5)) { alert in
                AlertRow(alert: alert)
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }

    private var detailsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Details")
                .font(.headline)

            if let notes = trip.notes, !notes.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Notes")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(notes)
                        .font(.subheadline)
                }
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("Created")
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text(trip.createdAt)
                    .font(.subheadline)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
    }

    private var actionsSection: some View {
        VStack(spacing: 12) {
            if trip.tripStatus == .planned {
                Button(action: markAsActive) {
                    Label("Start Trip", systemImage: "play.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
            } else if trip.tripStatus == .active {
                Button(action: markAsCompleted) {
                    Label("Complete Trip", systemImage: "checkmark.circle.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
            }
        }
    }

    private func formatDateRange() -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium

        if let start = trip.startDateFormatted, let end = trip.endDateFormatted {
            if start == end {
                return formatter.string(from: start)
            }
            return "\(formatter.string(from: start)) - \(formatter.string(from: end))"
        }
        return "\(trip.startDate) - \(trip.endDate)"
    }

    private func formatSnow(_ cm: Double) -> String {
        if useMetric {
            return String(format: "%.0f cm", cm)
        } else {
            return String(format: "%.1f\"", cm / 2.54)
        }
    }

    private func formatTemp(_ celsius: Double) -> String {
        if useMetric {
            return String(format: "%.0f°C", celsius)
        } else {
            return String(format: "%.0f°F", celsius * 9/5 + 32)
        }
    }

    private func refreshConditions() async {
        isRefreshing = true
        defer { isRefreshing = false }
        _ = try? await tripManager.refreshTripConditions(trip)
    }

    private func markAsActive() {
        Task {
            _ = try? await tripManager.updateTrip(
                trip,
                startDate: nil,
                endDate: nil,
                notes: nil,
                partySize: nil,
                status: .active
            )
        }
    }

    private func markAsCompleted() {
        Task {
            _ = try? await tripManager.updateTrip(
                trip,
                startDate: nil,
                endDate: nil,
                notes: nil,
                partySize: nil,
                status: .completed
            )
        }
    }
}

// MARK: - Alert Row

struct AlertRow: View {
    let alert: TripAlert

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: alert.type.icon)
                .foregroundColor(alert.isRead ? .secondary : .orange)
                .frame(width: 24)

            VStack(alignment: .leading, spacing: 2) {
                Text(alert.message)
                    .font(.subheadline)
                    .foregroundColor(alert.isRead ? .secondary : .primary)
                Text(alert.createdAt)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }

            Spacer()

            if !alert.isRead {
                Circle()
                    .fill(Color.orange)
                    .frame(width: 8, height: 8)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Create Trip View

struct CreateTripView: View {
    @ObservedObject var tripManager: TripPlanningManager
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager

    @Environment(\.dismiss) private var dismiss

    @State private var selectedResort: Resort?
    @State private var startDate = Date()
    @State private var endDate = Date().addingTimeInterval(86400 * 2) // 2 days later
    @State private var notes = ""
    @State private var partySize = 1
    @State private var isCreating = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                // Resort Selection
                Section("Resort") {
                    if let resort = selectedResort {
                        HStack {
                            Text(resort.name)
                            Spacer()
                            Button("Change") {
                                selectedResort = nil
                            }
                            .font(.caption)
                        }
                    } else {
                        NavigationLink(destination: ResortPickerView(selectedResort: $selectedResort)) {
                            Text("Select a Resort")
                                .foregroundColor(.secondary)
                        }
                    }
                }

                // Dates
                Section("Dates") {
                    DatePicker("Start Date", selection: $startDate, in: Date()..., displayedComponents: .date)
                    DatePicker("End Date", selection: $endDate, in: startDate..., displayedComponents: .date)
                }

                // Party
                Section("Group") {
                    Stepper("Party Size: \(partySize)", value: $partySize, in: 1...50)
                }

                // Notes
                Section("Notes (Optional)") {
                    TextEditor(text: $notes)
                        .frame(minHeight: 80)
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.red)
                    }
                }
            }
            .navigationTitle("Plan a Trip")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Create") {
                        createTrip()
                    }
                    .disabled(selectedResort == nil || isCreating)
                }
            }
            .overlay {
                if isCreating {
                    ProgressView("Creating trip...")
                        .padding()
                        .background(Color(.systemBackground))
                        .cornerRadius(8)
                        .shadow(radius: 4)
                }
            }
        }
    }

    private func createTrip() {
        guard let resort = selectedResort else { return }

        isCreating = true
        errorMessage = nil

        Task {
            do {
                _ = try await tripManager.createTrip(
                    resortId: resort.id,
                    startDate: startDate,
                    endDate: endDate,
                    notes: notes.isEmpty ? nil : notes,
                    partySize: partySize
                )
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
            }
            isCreating = false
        }
    }
}

// MARK: - Edit Trip View

struct EditTripView: View {
    let trip: Trip
    @ObservedObject var tripManager: TripPlanningManager

    @Environment(\.dismiss) private var dismiss

    @State private var startDate: Date
    @State private var endDate: Date
    @State private var notes: String
    @State private var partySize: Int
    @State private var isSaving = false
    @State private var errorMessage: String?

    init(trip: Trip, tripManager: TripPlanningManager) {
        self.trip = trip
        self.tripManager = tripManager

        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"

        _startDate = State(initialValue: formatter.date(from: trip.startDate) ?? Date())
        _endDate = State(initialValue: formatter.date(from: trip.endDate) ?? Date())
        _notes = State(initialValue: trip.notes ?? "")
        _partySize = State(initialValue: trip.partySize)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Resort") {
                    Text(trip.resortName)
                        .foregroundColor(.secondary)
                }

                Section("Dates") {
                    DatePicker("Start Date", selection: $startDate, displayedComponents: .date)
                    DatePicker("End Date", selection: $endDate, in: startDate..., displayedComponents: .date)
                }

                Section("Group") {
                    Stepper("Party Size: \(partySize)", value: $partySize, in: 1...50)
                }

                Section("Notes") {
                    TextEditor(text: $notes)
                        .frame(minHeight: 80)
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.red)
                    }
                }
            }
            .navigationTitle("Edit Trip")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Save") {
                        saveTrip()
                    }
                    .disabled(isSaving)
                }
            }
        }
    }

    private func saveTrip() {
        isSaving = true
        errorMessage = nil

        Task {
            do {
                _ = try await tripManager.updateTrip(
                    trip,
                    startDate: startDate,
                    endDate: endDate,
                    notes: notes.isEmpty ? nil : notes,
                    partySize: partySize,
                    status: nil
                )
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
            }
            isSaving = false
        }
    }
}

// MARK: - Resort Picker View

struct ResortPickerView: View {
    @Binding var selectedResort: Resort?
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager

    @Environment(\.dismiss) private var dismiss
    @State private var searchText = ""

    var filteredResorts: [Resort] {
        if searchText.isEmpty {
            return snowConditionsManager.resorts
        }
        return snowConditionsManager.resorts.filter {
            $0.name.localizedCaseInsensitiveContains(searchText) ||
            $0.country.localizedCaseInsensitiveContains(searchText) ||
            $0.region.localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        List(filteredResorts) { resort in
            Button(action: {
                selectedResort = resort
                dismiss()
            }) {
                HStack {
                    VStack(alignment: .leading) {
                        Text(resort.name)
                            .font(.headline)
                        Text(resort.displayLocation)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                    if selectedResort?.id == resort.id {
                        Image(systemName: "checkmark")
                            .foregroundColor(.blue)
                    }
                }
            }
            .foregroundColor(.primary)
        }
        .searchable(text: $searchText, prompt: "Search resorts")
        .navigationTitle("Select Resort")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Upcoming Trips Card (for Home Screen)

struct UpcomingTripsCard: View {
    @StateObject private var tripManager = TripPlanningManager()

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Upcoming Trips", systemImage: "calendar")
                    .font(.headline)
                Spacer()
                NavigationLink(destination: TripsListView()) {
                    Text("See All")
                        .font(.caption)
                        .foregroundColor(.blue)
                }
            }

            if tripManager.isLoading {
                HStack {
                    Spacer()
                    ProgressView()
                    Spacer()
                }
                .padding(.vertical, 20)
            } else if let nextTrip = tripManager.upcomingTrips.first {
                NavigationLink(destination: TripDetailView(trip: nextTrip, tripManager: tripManager)) {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(nextTrip.resortName)
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(.primary)

                            if let days = nextTrip.daysUntilTrip {
                                Text(days == 0 ? "Today!" : days == 1 ? "Tomorrow" : "In \(days) days")
                                    .font(.caption)
                                    .foregroundColor(.blue)
                            }
                        }

                        Spacer()

                        if nextTrip.unreadAlertCount > 0 {
                            HStack(spacing: 2) {
                                Image(systemName: "bell.fill")
                                    .font(.caption)
                                Text("\(nextTrip.unreadAlertCount)")
                                    .font(.caption)
                            }
                            .foregroundColor(.orange)
                        }
                    }
                }
                .buttonStyle(PlainButtonStyle())
            } else {
                HStack {
                    Image(systemName: "calendar.badge.plus")
                        .foregroundColor(.secondary)
                    Text("No trips planned")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .cornerRadius(12)
        .task {
            await tripManager.loadTrips()
        }
    }
}

#Preview {
    TripsListView()
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
}
