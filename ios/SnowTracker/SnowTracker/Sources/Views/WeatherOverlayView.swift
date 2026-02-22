import SwiftUI

/// Animated weather overlay for ResortDetailView.
/// Uses Canvas + TimelineView for performant particle rendering.
/// All overlays use `.allowsHitTesting(false)` to never block scrolling.
struct WeatherOverlayView: View {
    let overlayType: WeatherOverlayType

    var body: some View {
        switch overlayType {
        case .snow:
            SnowOverlay()
        case .sun:
            SunOverlay()
        case .wind:
            WindOverlay()
        case .none:
            EmptyView()
        }
    }
}

// MARK: - Snow Overlay

private struct SnowOverlay: View {
    @State private var particles: [SnowParticle] = (0..<30).map { _ in SnowParticle() }

    var body: some View {
        SwiftUI.TimelineView(.animation(minimumInterval: 1.0 / 30.0)) { timeline in
            Canvas { context, size in
                let time = timeline.date.timeIntervalSinceReferenceDate
                for particle in particles {
                    let x = particle.x(at: time, width: size.width)
                    let y = particle.y(at: time, height: size.height)
                    let rect = CGRect(
                        x: x - particle.radius,
                        y: y - particle.radius,
                        width: particle.radius * 2,
                        height: particle.radius * 2
                    )
                    context.opacity = particle.opacity
                    context.fill(Circle().path(in: rect), with: .color(.white))
                }
            }
        }
        .opacity(0.25)
        .allowsHitTesting(false)
    }
}

private struct SnowParticle {
    let startX: Double
    let speed: Double
    let phase: Double
    let radius: Double
    let opacity: Double
    let drift: Double

    init() {
        startX = Double.random(in: 0...1)
        speed = Double.random(in: 0.02...0.06)
        phase = Double.random(in: 0...(.pi * 2))
        radius = Double.random(in: 1.5...4.0)
        opacity = Double.random(in: 0.4...1.0)
        drift = Double.random(in: 15...30)
    }

    func x(at time: Double, width: Double) -> Double {
        let base = startX * width
        return base + sin(time * 0.8 + phase) * drift
    }

    func y(at time: Double, height: Double) -> Double {
        let progress = (time * speed + phase).truncatingRemainder(dividingBy: 1.2)
        return progress * height / 1.2
    }
}

// MARK: - Sun Overlay

private struct SunOverlay: View {
    var body: some View {
        SwiftUI.TimelineView(.animation(minimumInterval: 1.0 / 10.0)) { timeline in
            Canvas { context, size in
                let time = timeline.date.timeIntervalSinceReferenceDate
                let rotation = Angle.degrees(time.truncatingRemainder(dividingBy: 30) / 30 * 360)

                let center = CGPoint(x: size.width * 0.85, y: size.height * 0.05)
                let maxRadius = max(size.width, size.height) * 0.8

                context.translateBy(x: center.x, y: center.y)
                context.rotate(by: rotation)
                context.translateBy(x: -center.x, y: -center.y)

                // Warm radial glow
                let gradient = Gradient(stops: [
                    .init(color: Color(red: 1.0, green: 0.95, blue: 0.6).opacity(0.15), location: 0),
                    .init(color: Color(red: 1.0, green: 0.85, blue: 0.4).opacity(0.06), location: 0.4),
                    .init(color: Color.clear, location: 1.0)
                ])

                context.fill(
                    Ellipse().path(in: CGRect(
                        x: center.x - maxRadius,
                        y: center.y - maxRadius,
                        width: maxRadius * 2,
                        height: maxRadius * 2
                    )),
                    with: .radialGradient(
                        gradient,
                        center: center,
                        startRadius: 0,
                        endRadius: maxRadius
                    )
                )
            }
        }
        .opacity(0.12)
        .allowsHitTesting(false)
    }
}

// MARK: - Wind Overlay

private struct WindOverlay: View {
    @State private var streaks: [WindStreak] = (0..<15).map { _ in WindStreak() }

    var body: some View {
        SwiftUI.TimelineView(.animation(minimumInterval: 1.0 / 30.0)) { timeline in
            Canvas { context, size in
                let time = timeline.date.timeIntervalSinceReferenceDate
                for streak in streaks {
                    let x = streak.x(at: time, width: size.width)
                    let y = streak.y * size.height
                    let rect = CGRect(
                        x: x,
                        y: y - streak.thickness / 2,
                        width: streak.length,
                        height: streak.thickness
                    )
                    context.opacity = streak.opacity
                    context.fill(
                        RoundedRectangle(cornerRadius: streak.thickness / 2)
                            .path(in: rect),
                        with: .color(.white)
                    )
                }
            }
        }
        .opacity(0.2)
        .allowsHitTesting(false)
    }
}

private struct WindStreak {
    let y: Double
    let speed: Double
    let phase: Double
    let length: Double
    let thickness: Double
    let opacity: Double

    init() {
        y = Double.random(in: 0.05...0.95)
        speed = Double.random(in: 0.08...0.2)
        phase = Double.random(in: 0...1)
        length = Double.random(in: 30...80)
        thickness = Double.random(in: 1.0...2.5)
        opacity = Double.random(in: 0.3...0.8)
    }

    func x(at time: Double, width: Double) -> Double {
        let total = width + length
        let progress = ((time * speed + phase).truncatingRemainder(dividingBy: 1.0))
        return progress * total - length
    }
}
