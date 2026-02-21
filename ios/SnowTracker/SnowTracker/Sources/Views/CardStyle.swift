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
}
