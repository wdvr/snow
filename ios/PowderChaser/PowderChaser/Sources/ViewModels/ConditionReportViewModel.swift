import SwiftUI
import os.log

@MainActor
final class ConditionReportViewModel: ObservableObject {
    let resortId: String

    @Published var reports: [ConditionReport] = []
    @Published var summary: ConditionReportSummary?
    @Published var isLoading = false
    @Published var isSubmitting = false
    @Published var errorMessage: String?
    @Published var submitSuccess = false

    private let apiClient = APIClient.shared
    private let log = Logger(subsystem: "com.snowtracker.app", category: "ConditionReportVM")

    init(resortId: String) {
        self.resortId = resortId
    }

    func loadReports(limit: Int = 10) async {
        isLoading = true
        defer { isLoading = false }

        do {
            let response = try await apiClient.getConditionReports(resortId: resortId, limit: limit)
            reports = response.reports
            summary = response.summary
            errorMessage = nil
            log.debug("Loaded \(response.reports.count) condition reports for \(self.resortId)")
        } catch {
            log.error("Error loading condition reports: \(error.localizedDescription)")
            errorMessage = error.localizedDescription
        }
    }

    func submitReport(
        conditionType: ConditionType,
        score: Int,
        comment: String?,
        elevationLevel: ReportElevationLevel?
    ) async {
        isSubmitting = true
        submitSuccess = false
        defer { isSubmitting = false }

        do {
            let trimmedComment = comment?.trimmingCharacters(in: .whitespacesAndNewlines)
            let finalComment = (trimmedComment?.isEmpty == true) ? nil : trimmedComment

            try await apiClient.submitConditionReport(
                resortId: resortId,
                conditionType: conditionType.rawValue,
                score: score,
                comment: finalComment,
                elevationLevel: elevationLevel?.rawValue
            )
            submitSuccess = true
            errorMessage = nil
            log.debug("Submitted condition report for \(self.resortId)")

            // Reload reports to show the new one
            await loadReports()
        } catch {
            log.error("Error submitting condition report: \(error.localizedDescription)")
            errorMessage = error.localizedDescription
        }
    }

    func deleteReport(reportId: String) async {
        do {
            try await apiClient.deleteConditionReport(resortId: resortId, reportId: reportId)
            reports.removeAll { $0.reportId == reportId }
            log.debug("Deleted condition report \(reportId)")
        } catch {
            log.error("Error deleting condition report: \(error.localizedDescription)")
            errorMessage = error.localizedDescription
        }
    }
}
