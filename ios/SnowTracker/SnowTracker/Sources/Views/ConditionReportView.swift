import SwiftUI

// MARK: - Condition Report Section (embedded in ResortDetailView)

struct ConditionReportSection: View {
    let resortId: String
    @StateObject private var viewModel: ConditionReportViewModel
    @State private var showingSubmitSheet = false

    init(resortId: String) {
        self.resortId = resortId
        _viewModel = StateObject(wrappedValue: ConditionReportViewModel(resortId: resortId))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                Image(systemName: "person.3.fill")
                    .foregroundStyle(.blue)
                Text("Community Reports")
                    .font(.headline)

                Spacer()

                Button {
                    showingSubmitSheet = true
                } label: {
                    Label("Report", systemImage: "plus.circle.fill")
                        .font(.subheadline)
                        .fontWeight(.medium)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.small)
            }

            // Summary
            if let summary = viewModel.summary, summary.totalReports > 0 {
                summaryView(summary)
            }

            // Recent reports
            if viewModel.isLoading && viewModel.reports.isEmpty {
                HStack {
                    Spacer()
                    ProgressView()
                        .padding(.vertical, 8)
                    Spacer()
                }
            } else if viewModel.reports.isEmpty {
                Text("No reports yet. Be the first to report conditions!")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 4)
            } else {
                ForEach(viewModel.reports.prefix(3)) { report in
                    reportCard(report)
                }

                if viewModel.reports.count > 3 {
                    Text("\(viewModel.reports.count - 3) more reports")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .cardStyle()
        .sheet(isPresented: $showingSubmitSheet) {
            SubmitConditionReportView(viewModel: viewModel)
        }
        .task {
            await viewModel.loadReports()
        }
    }

    // MARK: - Summary View

    private func summaryView(_ summary: ConditionReportSummary) -> some View {
        HStack(spacing: 16) {
            // Average score
            if let avgScore = summary.averageScore {
                VStack(spacing: 2) {
                    Text(String(format: "%.1f", avgScore))
                        .font(.system(size: 20, weight: .bold, design: .rounded))
                        .foregroundStyle(scoreColor(for: avgScore))
                    Text("avg score")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            // Dominant condition
            if let dominant = summary.dominant {
                VStack(spacing: 2) {
                    Image(systemName: dominant.icon)
                        .font(.title3)
                        .foregroundStyle(dominant.color)
                    Text(dominant.displayName)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }

            // Recent reports count
            VStack(spacing: 2) {
                Text("\(summary.reportsLast24h)")
                    .font(.system(size: 20, weight: .bold, design: .rounded))
                    .foregroundStyle(.blue)
                Text("last 24h")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            Spacer()
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(summaryAccessibilityLabel(summary))
    }

    private func summaryAccessibilityLabel(_ summary: ConditionReportSummary) -> String {
        var parts: [String] = []
        if let avgScore = summary.averageScore {
            parts.append("Average score \(String(format: "%.1f", avgScore))")
        }
        if let dominant = summary.dominant {
            parts.append("Most reported: \(dominant.displayName)")
        }
        parts.append("\(summary.reportsLast24h) reports in last 24 hours")
        return parts.joined(separator: ". ")
    }

    // MARK: - Report Card

    private func reportCard(_ report: ConditionReport) -> some View {
        HStack(spacing: 10) {
            // Condition icon
            Image(systemName: report.condition.icon)
                .font(.title3)
                .foregroundStyle(report.condition.color)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(report.condition.displayName)
                        .font(.subheadline)
                        .fontWeight(.medium)

                    Text("\(report.score)/10")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundStyle(scoreColor(for: Double(report.score)))
                        .padding(.horizontal, 6)
                        .padding(.vertical, 1)
                        .background(
                            Capsule()
                                .fill(scoreColor(for: Double(report.score)).opacity(0.15))
                        )

                    if let elevation = report.elevation {
                        Text(elevation.displayName)
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 4)
                            .padding(.vertical, 1)
                            .background(
                                Capsule()
                                    .strokeBorder(Color.secondary.opacity(0.3), lineWidth: 0.5)
                            )
                    }
                }

                if let comment = report.comment, !comment.isEmpty {
                    Text(comment)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }

            Spacer()

            Text(report.formattedTimestamp)
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(reportAccessibilityLabel(report))
    }

    private func reportAccessibilityLabel(_ report: ConditionReport) -> String {
        var parts = ["\(report.condition.displayName) conditions", "score \(report.score) out of 10"]
        if let elevation = report.elevation {
            parts.append("at \(elevation.displayName)")
        }
        if let comment = report.comment, !comment.isEmpty {
            parts.append(comment)
        }
        parts.append(report.formattedTimestamp)
        return parts.joined(separator: ", ")
    }

    // MARK: - Helpers

    private func scoreColor(for score: Double) -> Color {
        switch score {
        case 0..<3: .red
        case 3..<5: .orange
        case 5..<7: .yellow
        case 7..<9: .green
        default: Color(red: 0.0, green: 0.65, blue: 0.35) // Emerald
        }
    }
}

// MARK: - Submit Condition Report View

struct SubmitConditionReportView: View {
    @ObservedObject var viewModel: ConditionReportViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var selectedCondition: ConditionType?
    @State private var score: Int = 5
    @State private var comment: String = ""
    @State private var selectedElevation: ReportElevationLevel?
    @State private var submitTrigger = false

    private let columns = Array(repeating: GridItem(.flexible(), spacing: 12), count: 4)

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    // Condition type selector
                    conditionTypeSection

                    // Score selector
                    scoreSection

                    // Elevation picker
                    elevationSection

                    // Comment
                    commentSection

                    // Submit button
                    submitButton
                }
                .padding()
            }
            .navigationTitle("Report Conditions")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
            .sensoryFeedback(.success, trigger: submitTrigger)
        }
    }

    // MARK: - Condition Type Section

    private var conditionTypeSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Snow Condition")
                .font(.headline)

            LazyVGrid(columns: columns, spacing: 12) {
                ForEach(ConditionType.allCases, id: \.self) { condition in
                    conditionButton(condition)
                }
            }
        }
    }

    private func conditionButton(_ condition: ConditionType) -> some View {
        let isSelected = selectedCondition == condition

        return Button {
            selectedCondition = condition
        } label: {
            VStack(spacing: 6) {
                Image(systemName: condition.icon)
                    .font(.title2)
                    .foregroundStyle(isSelected ? .white : condition.color)

                Text(condition.displayName)
                    .font(.caption2)
                    .fontWeight(.medium)
                    .foregroundStyle(isSelected ? .white : .primary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(
                RoundedRectangle(cornerRadius: 10)
                    .fill(isSelected ? condition.color : condition.color.opacity(0.1))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .strokeBorder(isSelected ? condition.color : .clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(condition.displayName) condition")
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }

    // MARK: - Score Section

    private var scoreSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Score")
                    .font(.headline)

                Spacer()

                Text(scoreDescription(for: score))
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundStyle(scoreColor(for: score))
            }

            HStack(spacing: 4) {
                ForEach(1...10, id: \.self) { value in
                    Button {
                        score = value
                    } label: {
                        Text("\(value)")
                            .font(.system(size: 14, weight: .semibold, design: .rounded))
                            .foregroundStyle(value == score ? .white : .primary)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 10)
                            .background(
                                RoundedRectangle(cornerRadius: 8)
                                    .fill(value == score ? scoreColor(for: value) : Color(.systemGray6))
                            )
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Score \(value)")
                    .accessibilityAddTraits(value == score ? .isSelected : [])
                }
            }

            // Score range labels
            HStack {
                Text("Terrible")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Spacer()
                Text("Epic")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
    }

    // MARK: - Elevation Section

    private var elevationSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Elevation (optional)")
                .font(.headline)

            HStack(spacing: 8) {
                elevationChip(nil, label: "Skip")

                ForEach(ReportElevationLevel.allCases, id: \.self) { level in
                    elevationChip(level, label: level.displayName)
                }
            }
        }
    }

    private func elevationChip(_ level: ReportElevationLevel?, label: String) -> some View {
        let isSelected = selectedElevation == level

        return Button {
            selectedElevation = level
        } label: {
            Text(label)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundStyle(isSelected ? .white : .primary)
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(
                    Capsule()
                        .fill(isSelected ? Color.blue : Color(.systemGray6))
                )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(label) elevation")
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }

    // MARK: - Comment Section

    private var commentSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Comment (optional)")
                    .font(.headline)

                Spacer()

                Text("\(comment.count)/500")
                    .font(.caption)
                    .foregroundStyle(comment.count > 450 ? .orange : .secondary)
            }

            TextEditor(text: $comment)
                .frame(minHeight: 80, maxHeight: 120)
                .padding(8)
                .background(Color(.systemGray6))
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .onChange(of: comment) { _, newValue in
                    if newValue.count > 500 {
                        comment = String(newValue.prefix(500))
                    }
                }
        }
    }

    // MARK: - Submit Button

    private var submitButton: some View {
        VStack(spacing: 8) {
            Button {
                guard let condition = selectedCondition else { return }
                Task {
                    await viewModel.submitReport(
                        conditionType: condition,
                        score: score,
                        comment: comment.isEmpty ? nil : comment,
                        elevationLevel: selectedElevation
                    )
                    if viewModel.submitSuccess {
                        submitTrigger.toggle()
                        // Delay dismiss to allow haptic feedback
                        try? await Task.sleep(nanoseconds: 300_000_000)
                        dismiss()
                    }
                }
            } label: {
                Group {
                    if viewModel.isSubmitting {
                        ProgressView()
                            .tint(.white)
                    } else {
                        Text("Submit Report")
                            .fontWeight(.semibold)
                    }
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
            }
            .buttonStyle(.borderedProminent)
            .disabled(selectedCondition == nil || viewModel.isSubmitting)

            // Error message
            if let error = viewModel.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .multilineTextAlignment(.center)
            }
        }
    }

    // MARK: - Helpers

    private func scoreDescription(for score: Int) -> String {
        switch score {
        case 1...2: "Terrible"
        case 3...4: "Poor"
        case 5...6: "Fair"
        case 7...8: "Good"
        case 9...10: "Epic"
        default: "Unknown"
        }
    }

    private func scoreColor(for score: Int) -> Color {
        switch score {
        case 1...2: .red
        case 3...4: .orange
        case 5...6: .yellow
        case 7...8: .green
        case 9...10: Color(red: 0.0, green: 0.65, blue: 0.35)
        default: .gray
        }
    }
}

#Preview("Condition Report Section") {
    ScrollView {
        ConditionReportSection(resortId: "big-white")
            .padding()
    }
}

#Preview("Submit Report") {
    SubmitConditionReportView(viewModel: ConditionReportViewModel(resortId: "big-white"))
}
