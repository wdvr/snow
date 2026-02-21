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
            NavigationLink(destination: ResortDetailView(resort: resort)) {
                FavoriteResortRow(resort: resort)
            }
            .simultaneousGesture(TapGesture().onEnded {
                AnalyticsService.shared.trackResortClicked(
                    resortId: resort.id,
                    resortName: resort.name,
                    source: "favorites"
                )
            })
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
                        .fill(displayQuality.color.opacity(0.2))
                        .frame(width: 50, height: 50)

                    Image(systemName: displayQuality.icon)
                        .font(.title2)
                        .foregroundStyle(displayQuality.color)
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
                Text(resort.name)
                    .font(.headline)

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

            // Arrow indicator
            Image(systemName: "chevron.right")
                .foregroundStyle(.secondary)
                .font(.caption)
        }
        .padding(.vertical, 8)
    }
}

#Preview("Favorites") {
    FavoritesView()
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
}
