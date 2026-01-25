import SwiftUI
import MapKit

// MARK: - Resort Map View

struct ResortMapView: View {
    @EnvironmentObject private var snowConditionsManager: SnowConditionsManager
    @ObservedObject private var locationManager = LocationManager.shared
    @Binding var selectedRegion: SkiRegion?

    @State private var cameraPosition: MapCameraPosition = .automatic
    @State private var selectedResort: Resort?
    @State private var showingDetail = false

    var filteredResorts: [Resort] {
        if let region = selectedRegion {
            return snowConditionsManager.resorts.filter { $0.inferredRegion == region }
        }
        return snowConditionsManager.resorts
    }

    var body: some View {
        ZStack {
            Map(position: $cameraPosition, selection: $selectedResort) {
                // User location
                UserAnnotation()

                // Resort annotations
                ForEach(filteredResorts) { resort in
                    if let basePoint = resort.baseElevation {
                        Annotation(resort.name, coordinate: basePoint.coordinate, anchor: .bottom) {
                            ResortMapAnnotation(
                                resort: resort,
                                condition: snowConditionsManager.getLatestCondition(for: resort.id),
                                isSelected: selectedResort?.id == resort.id
                            )
                        }
                        .tag(resort)
                    }
                }
            }
            .mapStyle(.standard(elevation: .realistic))
            .mapControls {
                MapUserLocationButton()
                MapCompass()
                MapScaleView()
            }

            // Location button overlay (when not authorized)
            if !locationManager.isAuthorized {
                VStack {
                    Spacer()
                    HStack {
                        Spacer()
                        Button {
                            locationManager.requestAuthorization()
                        } label: {
                            HStack {
                                Image(systemName: "location.fill")
                                Text("Enable Location")
                            }
                            .font(.subheadline.weight(.medium))
                            .padding(.horizontal, 16)
                            .padding(.vertical, 10)
                            .background(.ultraThinMaterial)
                            .clipShape(Capsule())
                        }
                        .padding()
                    }
                }
            }
        }
        .onChange(of: selectedResort) { _, newValue in
            if newValue != nil {
                showingDetail = true
            }
        }
        .sheet(isPresented: $showingDetail) {
            if let resort = selectedResort {
                NavigationStack {
                    ResortDetailView(resort: resort)
                        .navigationBarTitleDisplayMode(.inline)
                        .toolbar {
                            ToolbarItem(placement: .topBarTrailing) {
                                Button("Done") {
                                    showingDetail = false
                                    selectedResort = nil
                                }
                            }
                        }
                }
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
            }
        }
        .onAppear {
            // Request location when map appears
            if locationManager.needsAuthorization {
                // Don't auto-request, wait for user action
            } else if locationManager.isAuthorized {
                locationManager.requestLocation()
            }

            // Set initial camera position based on selected region
            updateCameraForRegion()
        }
        .onChange(of: selectedRegion) { _, _ in
            updateCameraForRegion()
        }
    }

    private func updateCameraForRegion() {
        guard !filteredResorts.isEmpty else { return }

        // Calculate bounds of all resorts
        let coordinates = filteredResorts.compactMap { $0.baseElevation?.coordinate }
        guard !coordinates.isEmpty else { return }

        let lats = coordinates.map { $0.latitude }
        let lons = coordinates.map { $0.longitude }

        let center = CLLocationCoordinate2D(
            latitude: (lats.min()! + lats.max()!) / 2,
            longitude: (lons.min()! + lons.max()!) / 2
        )

        let latDelta = max((lats.max()! - lats.min()!) * 1.5, 2.0)
        let lonDelta = max((lons.max()! - lons.min()!) * 1.5, 2.0)

        withAnimation(.easeInOut(duration: 0.5)) {
            cameraPosition = .region(MKCoordinateRegion(
                center: center,
                span: MKCoordinateSpan(latitudeDelta: latDelta, longitudeDelta: lonDelta)
            ))
        }
    }
}

// MARK: - Resort Map Annotation

struct ResortMapAnnotation: View {
    let resort: Resort
    let condition: WeatherCondition?
    let isSelected: Bool

    private var quality: SnowQuality {
        condition?.snowQuality ?? .unknown
    }

    var body: some View {
        VStack(spacing: 0) {
            // Pin head with snow quality
            ZStack {
                Circle()
                    .fill(quality.color)
                    .frame(width: isSelected ? 44 : 36, height: isSelected ? 44 : 36)
                    .shadow(color: .black.opacity(0.3), radius: 4, x: 0, y: 2)

                Image(systemName: quality.icon)
                    .font(isSelected ? .title3 : .body)
                    .foregroundColor(.white)
            }

            // Pin point
            Triangle()
                .fill(quality.color)
                .frame(width: 12, height: 8)
                .offset(y: -2)

            // Resort name (shown when selected)
            if isSelected {
                Text(resort.name)
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(.ultraThinMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .offset(y: 4)
            }
        }
        .animation(.spring(response: 0.3), value: isSelected)
    }
}

// MARK: - Triangle Shape

struct Triangle: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: rect.midX, y: rect.maxY))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.minY))
        path.closeSubpath()
        return path
    }
}

// MARK: - Preview

#Preview("Resort Map") {
    ResortMapView(selectedRegion: .constant(nil))
        .environmentObject(SnowConditionsManager())
        .environmentObject(UserPreferencesManager.shared)
}
