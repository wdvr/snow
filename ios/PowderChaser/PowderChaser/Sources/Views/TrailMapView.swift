import SwiftUI

/// Full-screen zoomable trail map image viewer.
/// Supports pinch-to-zoom, double-tap to zoom, and drag to pan.
struct TrailMapView: View {
    let url: URL
    let resortName: String

    @Environment(\.dismiss) private var dismiss
    @State private var scale: CGFloat = 1
    @State private var lastScale: CGFloat = 1
    @State private var offset: CGSize = .zero
    @State private var lastOffset: CGSize = .zero

    var body: some View {
        NavigationStack {
            GeometryReader { geo in
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let image):
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                            .scaleEffect(scale)
                            .offset(offset)
                            .gesture(
                                MagnifyGesture()
                                    .onChanged { value in
                                        let newScale = lastScale * value.magnification
                                        scale = max(1, min(newScale, 5))
                                    }
                                    .onEnded { _ in
                                        lastScale = scale
                                        if scale <= 1 {
                                            withAnimation(.easeOut(duration: 0.2)) {
                                                offset = .zero
                                                lastOffset = .zero
                                            }
                                        }
                                    }
                                    .simultaneously(
                                        with: DragGesture()
                                            .onChanged { value in
                                                guard scale > 1 else { return }
                                                offset = CGSize(
                                                    width: lastOffset.width + value.translation.width,
                                                    height: lastOffset.height + value.translation.height
                                                )
                                            }
                                            .onEnded { _ in
                                                lastOffset = offset
                                            }
                                    )
                            )
                            .onTapGesture(count: 2) {
                                withAnimation(.easeInOut(duration: 0.3)) {
                                    if scale > 1 {
                                        scale = 1
                                        lastScale = 1
                                        offset = .zero
                                        lastOffset = .zero
                                    } else {
                                        scale = 2.5
                                        lastScale = 2.5
                                    }
                                }
                            }
                            .frame(width: geo.size.width, height: geo.size.height)

                    case .failure:
                        VStack(spacing: 12) {
                            Image(systemName: "map.circle")
                                .font(.system(size: 48))
                                .foregroundStyle(.secondary)
                            Text("Failed to load trail map")
                                .foregroundStyle(.secondary)
                            Link("Open in Browser", destination: url)
                                .font(.callout)
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)

                    case .empty:
                        VStack(spacing: 12) {
                            ProgressView()
                            Text("Loading trail map...")
                                .font(.callout)
                                .foregroundStyle(.secondary)
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)

                    @unknown default:
                        EmptyView()
                    }
                }
            }
            .background(.black)
            .navigationTitle(resortName)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.title3)
                            .symbolRenderingMode(.hierarchical)
                            .foregroundStyle(.white)
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    ShareLink(item: url) {
                        Image(systemName: "square.and.arrow.up")
                            .foregroundStyle(.white)
                    }
                }
            }
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarBackground(Color.black, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
    }
}
