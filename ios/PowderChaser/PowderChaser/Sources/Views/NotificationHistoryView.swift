import SwiftUI

// MARK: - Bell Button (for toolbar)

struct NotificationBellButton: View {
    @ObservedObject var viewModel: NotificationHistoryViewModel
    @Binding var showingSheet: Bool

    var body: some View {
        Image(systemName: "bell.fill")
            .font(.body)
            .foregroundStyle(.primary)
            .overlay(alignment: .topTrailing) {
                if viewModel.unreadCount > 0 {
                    Text(viewModel.unreadCount > 99 ? "99+" : "\(viewModel.unreadCount)")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1)
                        .background(Capsule().fill(Color(red: 1, green: 0, blue: 0)))
                        .compositingGroup()
                        .padding(1.5)
                        .background(Capsule().fill(Color(.systemBackground)))
                        .offset(x: 10, y: -8)
                }
            }
            .onTapGesture { showingSheet = true }
            .accessibilityLabel("Notifications")
            .accessibilityValue(viewModel.unreadCount > 0 ? "\(viewModel.unreadCount) unread" : "No unread")
    }
}

// MARK: - Notification History View

struct NotificationHistoryView: View {
    @ObservedObject var viewModel: NotificationHistoryViewModel
    @ObservedObject private var pushService = PushNotificationService.shared
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if viewModel.isLoading && viewModel.notifications.isEmpty {
                    ProgressView("Loading notifications...")
                } else if viewModel.notifications.isEmpty {
                    emptyState
                } else {
                    notificationList
                }
            }
            .navigationTitle("Notifications")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Close") { dismiss() }
                }
                if !viewModel.notifications.isEmpty {
                    ToolbarItem(placement: .topBarTrailing) {
                        Menu {
                            if viewModel.unreadCount > 0 {
                                Button {
                                    Task { await viewModel.markAllAsRead() }
                                } label: {
                                    Label("Mark All as Read", systemImage: "envelope.open")
                                }
                            }
                            Button(role: .destructive) {
                                Task { await viewModel.deleteAllNotifications() }
                            } label: {
                                Label("Delete All", systemImage: "trash")
                            }
                        } label: {
                            Image(systemName: "ellipsis.circle")
                        }
                    }
                }
            }
            .task {
                await viewModel.loadNotifications()
            }
            .refreshable {
                await viewModel.loadNotifications()
                await viewModel.fetchUnreadCount()
            }
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "bell.slash")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)
            Text("No Notifications")
                .font(.title3)
                .fontWeight(.semibold)
            Text("Snow alerts and updates will appear here.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
    }

    // MARK: - Notification List

    private var notificationList: some View {
        List {
            ForEach(viewModel.notifications) { notification in
                NotificationRowView(notification: notification)
                    .contentShape(Rectangle())
                    .onTapGesture {
                        handleTap(notification)
                    }
                    .onAppear {
                        // Infinite scroll: load more when reaching last item
                        if notification.id == viewModel.notifications.last?.id {
                            Task { await viewModel.loadMore() }
                        }
                    }
                    .listRowBackground(notification.isUnread ? Color.blue.opacity(0.05) : Color.clear)
                    .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                        Button(role: .destructive) {
                            Task { await viewModel.deleteNotification(notification) }
                        } label: {
                            Label("Delete", systemImage: "trash")
                        }
                    }
            }
        }
        .listStyle(.plain)
    }

    // MARK: - Actions

    private func handleTap(_ notification: NotificationHistoryItem) {
        // Mark as read
        Task { await viewModel.markAsRead(notification) }

        // Navigate to resort via the existing push notification deep-link flow
        if let resortId = notification.resortId {
            dismiss()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                pushService.pendingResortId = resortId
            }
        }
    }
}

// MARK: - Notification Row View

struct NotificationRowView: View {
    let notification: NotificationHistoryItem

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // Type icon circle
            ZStack {
                Circle()
                    .fill(notification.alertType.color.opacity(0.15))
                    .frame(width: 40, height: 40)

                Image(systemName: notification.alertType.icon)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(notification.alertType.color)
            }

            // Content
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(notification.title)
                        .font(.subheadline)
                        .fontWeight(notification.isUnread ? .semibold : .regular)
                        .lineLimit(1)

                    Spacer()

                    Text(notification.formattedTimestamp)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Text(notification.body)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)

                if let resortName = notification.resortName {
                    HStack(spacing: 4) {
                        Image(systemName: "mountain.2")
                            .font(.system(size: 9))
                        Text(resortName)
                            .font(.caption2)
                    }
                    .foregroundStyle(.tertiary)
                }
            }

            // Unread dot
            if notification.isUnread {
                Circle()
                    .fill(.blue)
                    .frame(width: 8, height: 8)
                    .padding(.top, 4)
            }
        }
        .padding(.vertical, 4)
    }
}
