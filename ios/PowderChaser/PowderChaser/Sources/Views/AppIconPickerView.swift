import SwiftUI

struct AppIconPickerView: View {
    @State private var currentIcon: String? = UIApplication.shared.alternateIconName

    private let icons: [(name: String?, displayName: String, previewAsset: String, description: String)] = [
        (nil, "Classic", "AppIconPreview-Classic", "Original mountain design"),
        ("AppIcon-Mountain", "Mountain", "AppIconPreview-Mountain", "Mountain silhouette with snow"),
        ("AppIcon-Minimal", "Minimal", "AppIconPreview-Minimal", "Clean white on dark navy"),
        ("AppIcon-Gradient", "Gradient", "AppIconPreview-Gradient", "Blue to purple gradient"),
        ("AppIcon-Dark", "Dark", "AppIconPreview-Dark", "Dark theme with white accents"),
        ("AppIcon-Neon", "Neon", "AppIconPreview-Neon", "Bright cyan on black"),
        ("AppIcon-Warm", "Warm", "AppIconPreview-Warm", "Sunset gradient with snowflake"),
        ("AppIcon-Forest", "Forest", "AppIconPreview-Forest", "Green teal with pine trees"),
        ("AppIcon-Bold", "Bold", "AppIconPreview-Bold", "PC text on bold blue"),
    ]

    private let columns = [
        GridItem(.adaptive(minimum: 100), spacing: 16),
    ]

    var body: some View {
        ScrollView {
            LazyVGrid(columns: columns, spacing: 20) {
                ForEach(icons, id: \.displayName) { icon in
                    iconCell(icon)
                }
            }
            .padding()
        }
        .navigationTitle("App Icon")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            AnalyticsService.shared.trackScreen("AppIconPicker", screenClass: "AppIconPickerView")
        }
    }

    @ViewBuilder
    private func iconCell(_ icon: (name: String?, displayName: String, previewAsset: String, description: String)) -> some View {
        let isSelected = currentIcon == icon.name

        VStack(spacing: 8) {
            Image(icon.previewAsset)
                .resizable()
                .aspectRatio(contentMode: .fit)
                .frame(width: 68, height: 68)
                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .stroke(isSelected ? Color.accentColor : Color.clear, lineWidth: 3)
                )
                .shadow(color: isSelected ? Color.accentColor.opacity(0.3) : Color.black.opacity(0.1),
                        radius: isSelected ? 6 : 2,
                        y: isSelected ? 0 : 1)

            Text(icon.displayName)
                .font(.caption)
                .fontWeight(isSelected ? .semibold : .regular)

            Text(icon.description)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .lineLimit(2)
        }
        .padding(.vertical, 4)
        .onTapGesture {
            setIcon(icon.name)
        }
        .sensoryFeedback(.selection, trigger: currentIcon)
    }

    private func setIcon(_ name: String?) {
        guard currentIcon != name else { return }
        UIApplication.shared.setAlternateIconName(name) { error in
            if error == nil {
                currentIcon = name
                AnalyticsService.shared.trackSettingChanged(setting: "app_icon", value: name ?? "Classic")
            }
        }
    }
}

#Preview {
    NavigationStack {
        AppIconPickerView()
    }
}
