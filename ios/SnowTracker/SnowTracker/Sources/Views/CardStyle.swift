import SwiftUI

/// A consistent card style used across the app for content sections.
/// Applies padding, system background, rounded corners, and subtle shadow.
struct CardStyleModifier: ViewModifier {
    var cornerRadius: CGFloat = 12
    var shadowRadius: CGFloat = 2
    var elevated: Bool = false

    func body(content: Content) -> some View {
        content
            .padding()
            .background(Color(.systemBackground))
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
            .shadow(
                color: .black.opacity(elevated ? 0.12 : 0.08),
                radius: elevated ? 6 : shadowRadius,
                x: 0,
                y: elevated ? 2 : 1
            )
    }
}

extension View {
    func cardStyle(cornerRadius: CGFloat = 12, shadowRadius: CGFloat = 2) -> some View {
        modifier(CardStyleModifier(cornerRadius: cornerRadius, shadowRadius: shadowRadius))
    }

    func cardStyleElevated(cornerRadius: CGFloat = 12) -> some View {
        modifier(CardStyleModifier(cornerRadius: cornerRadius, elevated: true))
    }

    func cardStyleFrosted(cornerRadius: CGFloat = 12) -> some View {
        self
            .padding()
            .background(.ultraThinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius))
            .shadow(color: .black.opacity(0.08), radius: 2, x: 0, y: 1)
    }
}

// MARK: - Pass Badge

struct PassBadge: View {
    let passName: String
    let detail: String
    let color: Color

    init(passName: String, detail: String = "", color: Color) {
        self.passName = passName
        self.detail = detail
        self.color = color
    }

    var body: some View {
        HStack(spacing: 3) {
            Text(passName)
                .font(.caption2)
                .fontWeight(.bold)
            if !detail.isEmpty && detail != "Unlimited" {
                Text(detail)
                    .font(.caption2)
            }
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 2)
        .foregroundStyle(color)
        .background(color.opacity(0.12))
        .clipShape(RoundedRectangle(cornerRadius: 4))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(passName) Pass\(detail.isEmpty || detail == "Unlimited" ? "" : ": \(detail)")")
    }
}
