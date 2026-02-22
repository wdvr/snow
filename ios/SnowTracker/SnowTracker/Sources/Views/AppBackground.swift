import SwiftUI

/// Subtle gradient background for views across the app.
/// Light mode: faint blue-white to neutral to lavender.
/// Dark mode: deep navy-black for a mountain night feel.
struct AppBackgroundModifier: ViewModifier {
    @Environment(\.colorScheme) private var colorScheme

    func body(content: Content) -> some View {
        content
            .background(gradient.ignoresSafeArea())
    }

    private var gradient: LinearGradient {
        switch colorScheme {
        case .dark:
            // Very subtle — barely perceptible shift from pure black
            // so cards don't clash against the background
            return LinearGradient(
                colors: [
                    Color(red: 0.07, green: 0.07, blue: 0.09),
                    Color(red: 0.06, green: 0.06, blue: 0.08),
                    Color(red: 0.07, green: 0.07, blue: 0.10)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
        default:
            return LinearGradient(
                colors: [
                    Color(red: 0.95, green: 0.96, blue: 0.99),
                    Color(red: 0.97, green: 0.97, blue: 0.97),
                    Color(red: 0.96, green: 0.95, blue: 0.98)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
        }
    }
}

extension View {
    func appBackground() -> some View {
        modifier(AppBackgroundModifier())
    }
}
