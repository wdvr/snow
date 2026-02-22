import SwiftUI

struct FavoritesView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @State private var resortToRemove: Resort?
    @State private var showingGroupManager = false
    @State private var showingMoveSheet = false
    @State private var resortToMove: Resort?

    private var favoriteResorts: [Resort] {
        snowConditionsManager.resorts
            .filter { userPreferencesManager.favoriteResorts.contains($0.id) }
            .sorted { resort1, resort2 in
                let q1 = snowConditionsManager.getSnowQuality(for: resort1.id).sortOrder
                let q2 = snowConditionsManager.getSnowQuality(for: resort2.id).sortOrder
                if q1 != q2 { return q1 < q2 }
                return resort1.name < resort2.name
            }
    }

    var body: some View {
        NavigationStack {
            Group {
                if favoriteResorts.isEmpty {
                    emptyStateView
                } else {
                    favoritesList
                }
            }
            .navigationTitle("Favorites")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    if !favoriteResorts.isEmpty {
                        Button {
                            showingGroupManager = true
                        } label: {
                            Label("Groups", systemImage: "folder")
                        }
                    }
                }
                if favoriteResorts.count >= 2 {
                    ToolbarItem(placement: .topBarTrailing) {
                        NavigationLink {
                            ResortComparisonView(initialResorts: favoriteResorts)
                                .environmentObject(snowConditionsManager)
                                .environmentObject(userPreferencesManager)
                        } label: {
                            Label("Compare", systemImage: "rectangle.split.3x1")
                        }
                    }
                }
            }
            .onAppear {
                AnalyticsService.shared.trackScreen("Favorites", screenClass: "FavoritesView")
            }
            .onDisappear {
                AnalyticsService.shared.trackScreenExit("Favorites")
            }
            .refreshable {
                AnalyticsService.shared.trackPullToRefresh(screen: "Favorites")
                await snowConditionsManager.fetchConditionsForFavorites()
            }
            .task {
                await snowConditionsManager.fetchConditionsForFavorites()
            }
            .navigationDestination(for: Resort.self) { resort in
                ResortDetailView(resort: resort)
            }
            .sheet(isPresented: $showingGroupManager) {
                FavoriteGroupsManagerView()
                    .environmentObject(userPreferencesManager)
            }
            .sheet(isPresented: $showingMoveSheet) {
                if let resort = resortToMove {
                    MoveToGroupSheet(resort: resort)
                        .environmentObject(userPreferencesManager)
                }
            }
        }
    }

    private var emptyStateView: some View {
        VStack(spacing: 20) {
            Image(systemName: "heart.slash")
                .font(.system(size: 60))
                .foregroundStyle(.gray)

            Text("No Favorites Yet")
                .font(.title2)
                .fontWeight(.semibold)

            Text("Tap the heart icon on any resort to add it to your favorites for quick access.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)

            NavigationLink(destination: ResortListView()) {
                Label("Browse Resorts", systemImage: "mountain.2")
                    .font(.headline)
                    .padding()
                    .background(Color.blue)
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
    }

    private var favoritesList: some View {
        List {
            // Conditions summary card
            if favoriteResorts.count >= 2 {
                Section {
                    FavoritesSummaryCard(
                        resorts: favoriteResorts,
                        snowConditionsManager: snowConditionsManager,
                        userPreferencesManager: userPreferencesManager
                    )
                }
                .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 4, trailing: 16))
                .listRowBackground(Color.clear)
                .listRowSeparator(.hidden)
            }

            // Show grouped sections if any groups exist
            if !userPreferencesManager.favoriteGroups.isEmpty {
                // Grouped resorts
                ForEach(userPreferencesManager.favoriteGroups) { group in
                    let groupResorts = favoriteResorts.filter { group.resortIds.contains($0.id) }
                    if !groupResorts.isEmpty {
                        Section(group.name) {
                            resortRows(groupResorts)
                        }
                    }
                }

                // Ungrouped resorts
                let ungroupedIds = userPreferencesManager.ungroupedFavoriteResortIds()
                let ungrouped = favoriteResorts.filter { ungroupedIds.contains($0.id) }
                if !ungrouped.isEmpty {
                    Section("Other") {
                        resortRows(ungrouped)
                    }
                }
            } else {
                // No groups - flat list
                resortRows(favoriteResorts)
            }
        }
        .listStyle(PlainListStyle())
        .alert("Remove Favorite?", isPresented: Binding(
            get: { resortToRemove != nil },
            set: { if !$0 { resortToRemove = nil } }
        )) {
            Button("Cancel", role: .cancel) { resortToRemove = nil }
            Button("Remove", role: .destructive) {
                if let resort = resortToRemove {
                    userPreferencesManager.toggleFavorite(resortId: resort.id)
                }
                resortToRemove = nil
            }
        } message: {
            if let resort = resortToRemove {
                Text("Remove \(resort.name) from your favorites?")
            }
        }
    }

    private func resortRows(_ resorts: [Resort]) -> some View {
        ForEach(resorts) { resort in
            NavigationLink(value: resort) {
                FavoriteResortRow(resort: resort)
            }
            .accessibilityLabel("\(resort.name), \(snowConditionsManager.getSnowQuality(for: resort.id).displayName)")
            .swipeActions(edge: .leading) {
                if !userPreferencesManager.favoriteGroups.isEmpty {
                    Button {
                        resortToMove = resort
                        showingMoveSheet = true
                    } label: {
                        Label("Move", systemImage: "folder")
                    }
                    .tint(.blue)
                }
            }
            .swipeActions(edge: .trailing) {
                Button(role: .destructive) {
                    resortToRemove = resort
                } label: {
                    Label("Remove", systemImage: "heart.slash")
                }
            }
        }
    }
}

// MARK: - Favorite Groups Manager

struct FavoriteGroupsManagerView: View {
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @Environment(\.dismiss) private var dismiss
    @State private var newGroupName = ""
    @State private var editingGroup: FavoriteGroup?
    @State private var editName = ""

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack {
                        TextField("New group name", text: $newGroupName)
                            .textInputAutocapitalization(.words)
                        Button {
                            guard !newGroupName.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                            userPreferencesManager.createGroup(name: newGroupName.trimmingCharacters(in: .whitespaces))
                            newGroupName = ""
                        } label: {
                            Image(systemName: "plus.circle.fill")
                                .foregroundStyle(.blue)
                        }
                        .disabled(newGroupName.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                } header: {
                    Text("Create Group")
                }

                if !userPreferencesManager.favoriteGroups.isEmpty {
                    Section {
                        ForEach(userPreferencesManager.favoriteGroups) { group in
                            HStack {
                                Image(systemName: "folder.fill")
                                    .foregroundStyle(.blue)
                                VStack(alignment: .leading) {
                                    Text(group.name)
                                        .font(.body)
                                    Text("\(group.resortIds.count) resorts")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                            }
                            .swipeActions(edge: .trailing) {
                                Button(role: .destructive) {
                                    userPreferencesManager.deleteGroup(id: group.id)
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                                Button {
                                    editingGroup = group
                                    editName = group.name
                                } label: {
                                    Label("Rename", systemImage: "pencil")
                                }
                                .tint(.orange)
                            }
                        }
                        .onMove { from, to in
                            userPreferencesManager.favoriteGroups.move(fromOffsets: from, toOffset: to)
                            userPreferencesManager.saveFavoriteGroups()
                        }
                    } header: {
                        Text("Your Groups")
                    }
                }
            }
            .navigationTitle("Manage Groups")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
                ToolbarItem(placement: .topBarLeading) {
                    EditButton()
                }
            }
            .alert("Rename Group", isPresented: Binding(
                get: { editingGroup != nil },
                set: { if !$0 { editingGroup = nil } }
            )) {
                TextField("Group name", text: $editName)
                Button("Cancel", role: .cancel) { editingGroup = nil }
                Button("Save") {
                    if let group = editingGroup {
                        userPreferencesManager.renameGroup(id: group.id, name: editName)
                    }
                    editingGroup = nil
                }
            }
        }
    }
}

// MARK: - Move to Group Sheet

struct MoveToGroupSheet: View {
    let resort: Resort
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager
    @Environment(\.dismiss) private var dismiss

    private var currentGroup: FavoriteGroup? {
        userPreferencesManager.groupForResort(resort.id)
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Button {
                        if let group = currentGroup {
                            userPreferencesManager.removeResortFromGroup(resortId: resort.id, groupId: group.id)
                        }
                        dismiss()
                    } label: {
                        HStack {
                            Label("No Group", systemImage: "tray")
                            Spacer()
                            if currentGroup == nil {
                                Image(systemName: "checkmark")
                                    .foregroundStyle(.blue)
                            }
                        }
                    }
                    .foregroundStyle(.primary)

                    ForEach(userPreferencesManager.favoriteGroups) { group in
                        Button {
                            userPreferencesManager.addResortToGroup(resortId: resort.id, groupId: group.id)
                            dismiss()
                        } label: {
                            HStack {
                                Label(group.name, systemImage: "folder.fill")
                                Spacer()
                                if currentGroup?.id == group.id {
                                    Image(systemName: "checkmark")
                                        .foregroundStyle(.blue)
                                }
                            }
                        }
                        .foregroundStyle(.primary)
                    }
                } header: {
                    Text("Move \"\(resort.name)\" to:")
                }
            }
            .navigationTitle("Move to Group")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium])
    }
}

// MARK: - Favorite Resort Row

struct FavoriteResortRow: View {
    let resort: Resort
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @EnvironmentObject private var userPreferencesManager: UserPreferencesManager

    private var topCondition: WeatherCondition? {
        snowConditionsManager.conditions[resort.id]?.first { $0.elevationLevel == "top" }
    }

    var body: some View {
        HStack(spacing: 12) {
            // Snow quality indicator - use overall quality for consistency
            let displayQuality = snowConditionsManager.getSnowQuality(for: resort.id)
            if displayQuality != .unknown {
                ZStack {
                    Circle()
                        .fill(
                            LinearGradient(
                                colors: [displayQuality.color.opacity(0.25), displayQuality.color.opacity(0.1)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 50, height: 50)

                    VStack(spacing: 0) {
                        if let score = snowConditionsManager.getSnowScore(for: resort.id) {
                            Text("\(score)")
                                .font(.caption.weight(.bold))
                                .fontDesign(.rounded)
                                .foregroundStyle(displayQuality.color)
                        } else {
                            Image(systemName: displayQuality.icon)
                                .font(.title3)
                                .foregroundStyle(displayQuality.color)
                        }
                    }
                }
            } else {
                ZStack {
                    Circle()
                        .fill(Color.gray.opacity(0.2))
                        .frame(width: 50, height: 50)

                    Image(systemName: "questionmark")
                        .font(.title2)
                        .foregroundStyle(.gray)
                }
            }

            // Resort info
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(resort.name)
                        .font(.headline)

                    if resort.epicPass != nil {
                        Text("Epic")
                            .font(.caption2)
                            .fontWeight(.semibold)
                            .padding(.horizontal, 5)
                            .padding(.vertical, 2)
                            .foregroundStyle(.indigo)
                            .background(Color.indigo.opacity(0.12))
                            .clipShape(RoundedRectangle(cornerRadius: 4))
                    }
                    if resort.ikonPass != nil {
                        Text("Ikon")
                            .font(.caption2)
                            .fontWeight(.semibold)
                            .padding(.horizontal, 5)
                            .padding(.vertical, 2)
                            .foregroundStyle(.orange)
                            .background(Color.orange.opacity(0.12))
                            .clipShape(RoundedRectangle(cornerRadius: 4))
                    }
                }

                Text(resort.displayLocation)
                    .font(.caption)
                    .foregroundStyle(.secondary)

                if let condition = topCondition {
                    HStack(spacing: 8) {
                        Label(condition.formattedTemperature(userPreferencesManager.preferredUnits), systemImage: "thermometer")
                        Label(condition.formattedFreshSnowWithPrefs(userPreferencesManager.preferredUnits), systemImage: "snowflake")
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
            }

            Spacer()

            // Forecast badge when significant snow is expected
            if let condition = topCondition,
               let predicted48h = condition.predictedSnow48hCm,
               predicted48h >= 5 {
                ForecastBadge(hours: 48, cm: predicted48h, prefs: userPreferencesManager.preferredUnits)
            }

            // Arrow indicator
            Image(systemName: "chevron.right")
                .foregroundStyle(.secondary)
                .font(.caption)
        }
        .padding(.vertical, 8)
    }
}

// MARK: - Favorites Summary Card

struct FavoritesSummaryCard: View {
    let resorts: [Resort]
    let snowConditionsManager: SnowConditionsManager
    let userPreferencesManager: UserPreferencesManager

    private var qualityCounts: [(quality: SnowQuality, count: Int)] {
        var counts: [SnowQuality: Int] = [:]
        for resort in resorts {
            let quality = snowConditionsManager.getSnowQuality(for: resort.id)
            if quality != .unknown {
                counts[quality, default: 0] += 1
            }
        }
        return counts.sorted { $0.key.sortOrder < $1.key.sortOrder }
            .map { (quality: $0.key, count: $0.value) }
    }

    private var bestResort: (resort: Resort, score: Int)? {
        resorts.compactMap { resort -> (Resort, Int)? in
            guard let score = snowConditionsManager.getSnowScore(for: resort.id) else { return nil }
            return (resort, score)
        }
        .max { $0.1 < $1.1 }
    }

    private var averageScore: Int? {
        let scores = resorts.compactMap { snowConditionsManager.getSnowScore(for: $0.id) }
        guard !scores.isEmpty else { return nil }
        return scores.reduce(0, +) / scores.count
    }

    private var totalFreshSnow: Double {
        resorts.compactMap { snowConditionsManager.snowQualitySummaries[$0.id]?.snowfallFreshCm }
            .reduce(0, +)
    }

    var body: some View {
        VStack(spacing: 12) {
            // Header row
            HStack {
                Label("Conditions Overview", systemImage: "chart.bar.fill")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.primary)
                Spacer()
            }

            // Best resort highlight
            if let best = bestResort {
                let quality = snowConditionsManager.getSnowQuality(for: best.resort.id)
                HStack(spacing: 10) {
                    ZStack {
                        Circle()
                            .fill(quality.color.opacity(0.15))
                            .frame(width: 36, height: 36)
                        Text("\(best.score)")
                            .font(.caption.weight(.bold))
                            .fontDesign(.rounded)
                            .foregroundStyle(quality.color)
                    }

                    VStack(alignment: .leading, spacing: 1) {
                        Text("Best conditions")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                        Text(best.resort.name)
                            .font(.caption.weight(.medium))
                    }

                    Spacer()

                    if let avg = averageScore {
                        VStack(alignment: .trailing, spacing: 1) {
                            Text("Avg score")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                            Text("\(avg)")
                                .font(.caption.weight(.medium))
                                .fontDesign(.rounded)
                        }
                    }
                }
            }

            // Quality distribution bar
            if !qualityCounts.isEmpty {
                let total = qualityCounts.reduce(0) { $0 + $1.count }
                VStack(spacing: 4) {
                    GeometryReader { geometry in
                        HStack(spacing: 1) {
                            ForEach(qualityCounts, id: \.quality) { item in
                                let width = max(8, geometry.size.width * CGFloat(item.count) / CGFloat(total))
                                RoundedRectangle(cornerRadius: 3)
                                    .fill(item.quality.color)
                                    .frame(width: width, height: 8)
                            }
                        }
                    }
                    .frame(height: 8)

                    // Legend
                    HStack(spacing: 8) {
                        ForEach(qualityCounts, id: \.quality) { item in
                            HStack(spacing: 3) {
                                Circle()
                                    .fill(item.quality.color)
                                    .frame(width: 6, height: 6)
                                Text("\(item.count) \(item.quality.displayName)")
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        Spacer()
                    }
                }
            }
        }
        .cardStyle()
    }
}

#Preview("Favorites") {
    FavoritesView()
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
}
