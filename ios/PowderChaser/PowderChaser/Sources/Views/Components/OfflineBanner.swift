import SwiftUI

/// A small banner displayed at the top of the screen when the device is offline.
/// Shows how long ago data was last cached so the user understands they are
/// viewing potentially stale information.
struct OfflineBanner: View {
    let cachedDataAge: String?

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "wifi.slash")
                .font(.subheadline)

            if let age = cachedDataAge {
                Text("Offline \u{2014} Showing cached data from \(age)")
                    .font(.subheadline)
            } else {
                Text("Offline \u{2014} Showing cached data")
                    .font(.subheadline)
            }
        }
        .foregroundStyle(.black.opacity(0.8))
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .padding(.horizontal, 16)
        .background(Color.yellow.opacity(0.85))
    }
}

#Preview("Offline Banner") {
    VStack {
        OfflineBanner(cachedDataAge: "5 min. ago")
        Spacer()
    }
}
