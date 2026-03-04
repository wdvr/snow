import SwiftUI

/// Subtle gradient background for views across the app.
/// Light mode: faint warm red-white tones.
/// Dark mode: deep dark red for a warm mountain feel.
struct AppBackgroundModifier: ViewModifier {
    @Environment(\.colorScheme) private var colorScheme

    func body(content: Content) -> some View {
        content
            .background(gradient.ignoresSafeArea())
    }

    private var gradient: LinearGradient {
        switch colorScheme {
        case .dark:
            // Subtle dark red tones
            return LinearGradient(
                colors: [
                    Color(red: 0.12, green: 0.04, blue: 0.04),
                    Color(red: 0.10, green: 0.03, blue: 0.03),
                    Color(red: 0.13, green: 0.04, blue: 0.05)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
        default:
            return LinearGradient(
                colors: [
                    Color(red: 0.99, green: 0.93, blue: 0.93),
                    Color(red: 0.98, green: 0.95, blue: 0.95),
                    Color(red: 0.99, green: 0.94, blue: 0.94)
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
