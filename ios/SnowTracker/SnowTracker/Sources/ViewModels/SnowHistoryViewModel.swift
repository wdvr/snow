import Foundation

@MainActor
final class SnowHistoryViewModel: ObservableObject {
    @Published var history: [DailySnowHistory] = []
    @Published var seasonSummary: SeasonSummary?
    @Published var isLoading = false
    @Published var error: String?

    func loadHistory(resortId: String, season: String? = nil) async {
        isLoading = true
        defer { isLoading = false }

        do {
            let response = try await APIClient.shared.getSnowHistory(
                resortId: resortId, season: season
            )
            history = response.history
            seasonSummary = response.seasonSummary
        } catch {
            self.error = error.localizedDescription
        }
    }
}
