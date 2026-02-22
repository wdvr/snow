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
            return LinearGradient(
                colors: [
                    Color(red: 0.06, green: 0.08, blue: 0.14),
                    Color(red: 0.08, green: 0.10, blue: 0.16),
                    Color(red: 0.07, green: 0.09, blue: 0.18)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
        default:
            return LinearGradient(
                colors: [
                    Color(red: 0.94, green: 0.96, blue: 1.0),
                    Color(red: 0.97, green: 0.97, blue: 0.97),
                    Color(red: 0.96, green: 0.94, blue: 0.98)
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
