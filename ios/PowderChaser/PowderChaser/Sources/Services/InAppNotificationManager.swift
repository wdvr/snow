import SwiftUI
import os.log

// MARK: - In-App Notification Model

struct InAppNotification: Identifiable, Equatable {
    let id = UUID()
    let title: String
    let body: String
    let resortId: String?
    let notificationType: String?
}

// MARK: - In-App Notification Manager

@MainActor
final class InAppNotificationManager: ObservableObject {
    static let shared = InAppNotificationManager()

    @Published var currentNotification: InAppNotification?

    private var dismissTask: Task<Void, Never>?
    private let log = Logger(subsystem: "com.snowtracker.app", category: "InAppNotification")

    private init() {}

    func show(title: String, body: String, resortId: String? = nil, notificationType: String? = nil) {
        // Cancel any pending dismiss
        dismissTask?.cancel()

        withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
            currentNotification = InAppNotification(
                title: title,
                body: body,
                resortId: resortId,
                notificationType: notificationType
            )
        }

        // Auto-dismiss after 4 seconds
        dismissTask = Task {
            try? await Task.sleep(for: .seconds(4))
            guard !Task.isCancelled else { return }
            dismiss()
        }
    }

    func dismiss() {
        dismissTask?.cancel()
        withAnimation(.easeOut(duration: 0.3)) {
            currentNotification = nil
        }
    }
}

// MARK: - In-App Notification Overlay View

struct InAppNotificationOverlay: View {
    @ObservedObject private var manager = InAppNotificationManager.shared
    var onTap: ((String?) -> Void)?

    var body: some View {
        VStack {
            if let notification = manager.currentNotification {
                notificationCard(notification)
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .zIndex(100)
            }
            Spacer()
        }
        .animation(.spring(response: 0.4, dampingFraction: 0.8), value: manager.currentNotification)
    }

    @ViewBuilder
    private func notificationCard(_ notification: InAppNotification) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "bell.fill")
                .font(.system(size: 20))
                .foregroundStyle(.blue)

            VStack(alignment: .leading, spacing: 2) {
                Text(notification.title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.primary)
                    .lineLimit(1)

                Text(notification.body)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            Spacer()

            Button {
                manager.dismiss()
            } label: {
                Image(systemName: "xmark")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
                .shadow(color: .black.opacity(0.15), radius: 12, x: 0, y: 4)
        )
        .padding(.horizontal, 12)
        .padding(.top, 4)
        .contentShape(Rectangle())
        .onTapGesture {
            manager.dismiss()
            onTap?(notification.resortId)
        }
    }
}
