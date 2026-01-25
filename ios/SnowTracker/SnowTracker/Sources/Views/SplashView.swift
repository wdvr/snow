import SwiftUI

struct SplashView: View {
    @State private var isAnimating = false
    @State private var showTitle = false
    @State private var showSubtitle = false
    @State private var snowflakes: [Snowflake] = []

    private let numberOfSnowflakes = 50

    var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Background gradient
                LinearGradient(
                    gradient: Gradient(colors: [
                        Color(red: 0.1, green: 0.2, blue: 0.4),
                        Color(red: 0.2, green: 0.4, blue: 0.6),
                        Color(red: 0.4, green: 0.6, blue: 0.8)
                    ]),
                    startPoint: .top,
                    endPoint: .bottom
                )
                .ignoresSafeArea()

                // Snowflakes
                ForEach(snowflakes) { snowflake in
                    SnowflakeView(snowflake: snowflake, isAnimating: isAnimating)
                }

                // Mountain silhouette
                MountainView()
                    .offset(y: geometry.size.height * 0.15)
                    .opacity(isAnimating ? 1 : 0)
                    .animation(.easeIn(duration: 0.8).delay(0.2), value: isAnimating)

                // Content
                VStack(spacing: 20) {
                    // App icon/logo
                    ZStack {
                        Circle()
                            .fill(.white.opacity(0.2))
                            .frame(width: 120, height: 120)
                            .blur(radius: 10)

                        Image(systemName: "snowflake")
                            .font(.system(size: 60, weight: .light))
                            .foregroundStyle(.white)
                            .rotationEffect(.degrees(isAnimating ? 360 : 0))
                            .animation(
                                .linear(duration: 20).repeatForever(autoreverses: false),
                                value: isAnimating
                            )
                    }
                    .scaleEffect(isAnimating ? 1 : 0.5)
                    .opacity(isAnimating ? 1 : 0)
                    .animation(.spring(response: 0.6, dampingFraction: 0.7).delay(0.1), value: isAnimating)

                    // App title
                    VStack(spacing: 8) {
                        Text("Snow Tracker")
                            .font(.system(size: 36, weight: .bold, design: .rounded))
                            .foregroundStyle(.white)
                            .opacity(showTitle ? 1 : 0)
                            .offset(y: showTitle ? 0 : 20)
                            .animation(.easeOut(duration: 0.5).delay(0.3), value: showTitle)

                        Text("Fresh powder awaits")
                            .font(.system(size: 16, weight: .medium, design: .rounded))
                            .foregroundStyle(.white.opacity(0.8))
                            .opacity(showSubtitle ? 1 : 0)
                            .offset(y: showSubtitle ? 0 : 10)
                            .animation(.easeOut(duration: 0.5).delay(0.5), value: showSubtitle)
                    }
                }
                .offset(y: -geometry.size.height * 0.1)

                // Loading indicator
                VStack {
                    Spacer()
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .scaleEffect(1.2)
                        .opacity(showSubtitle ? 1 : 0)
                        .animation(.easeIn(duration: 0.3).delay(0.7), value: showSubtitle)
                    Spacer()
                        .frame(height: geometry.size.height * 0.15)
                }
            }
        }
        .onAppear {
            generateSnowflakes()
            withAnimation {
                isAnimating = true
            }
            showTitle = true
            showSubtitle = true
        }
    }

    private func generateSnowflakes() {
        snowflakes = (0..<numberOfSnowflakes).map { _ in
            Snowflake(
                x: CGFloat.random(in: 0...1),
                y: CGFloat.random(in: -0.2...1),
                size: CGFloat.random(in: 4...12),
                opacity: Double.random(in: 0.3...0.8),
                speed: Double.random(in: 4...10),
                delay: Double.random(in: 0...3)
            )
        }
    }
}

struct Snowflake: Identifiable {
    let id = UUID()
    let x: CGFloat
    let y: CGFloat
    let size: CGFloat
    let opacity: Double
    let speed: Double
    let delay: Double
}

struct SnowflakeView: View {
    let snowflake: Snowflake
    let isAnimating: Bool

    @State private var yOffset: CGFloat = 0

    var body: some View {
        GeometryReader { geometry in
            Circle()
                .fill(.white.opacity(snowflake.opacity))
                .frame(width: snowflake.size, height: snowflake.size)
                .position(
                    x: geometry.size.width * snowflake.x,
                    y: geometry.size.height * snowflake.y + yOffset
                )
                .onAppear {
                    guard isAnimating else { return }
                    withAnimation(
                        .linear(duration: snowflake.speed)
                        .repeatForever(autoreverses: false)
                        .delay(snowflake.delay)
                    ) {
                        yOffset = geometry.size.height * 1.3
                    }
                }
        }
    }
}

struct MountainView: View {
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Back mountain (darker)
                MountainShape(peakOffset: 0.3, heightRatio: 0.5)
                    .fill(Color(red: 0.15, green: 0.25, blue: 0.35).opacity(0.8))
                    .offset(x: -geometry.size.width * 0.1)

                // Middle mountain
                MountainShape(peakOffset: 0.5, heightRatio: 0.55)
                    .fill(Color(red: 0.2, green: 0.3, blue: 0.4).opacity(0.9))

                // Front mountain (lighter with snow cap)
                ZStack {
                    MountainShape(peakOffset: 0.6, heightRatio: 0.45)
                        .fill(Color(red: 0.25, green: 0.35, blue: 0.45))

                    // Snow cap
                    SnowCapShape(peakOffset: 0.6, heightRatio: 0.45)
                        .fill(.white.opacity(0.9))
                }
                .offset(x: geometry.size.width * 0.15)
            }
        }
    }
}

struct MountainShape: Shape {
    let peakOffset: CGFloat
    let heightRatio: CGFloat

    func path(in rect: CGRect) -> Path {
        var path = Path()

        let peakX = rect.width * peakOffset
        let peakY = rect.height * (1 - heightRatio)

        path.move(to: CGPoint(x: 0, y: rect.height))
        path.addLine(to: CGPoint(x: peakX, y: peakY))
        path.addLine(to: CGPoint(x: rect.width, y: rect.height))
        path.closeSubpath()

        return path
    }
}

struct SnowCapShape: Shape {
    let peakOffset: CGFloat
    let heightRatio: CGFloat

    func path(in rect: CGRect) -> Path {
        var path = Path()

        let peakX = rect.width * peakOffset
        let peakY = rect.height * (1 - heightRatio)
        let snowLineY = peakY + rect.height * 0.08

        // Calculate intersection points
        let leftSlope = (rect.height - peakY) / peakX
        let rightSlope = (rect.height - peakY) / (rect.width - peakX)

        let leftX = (snowLineY - peakY) / leftSlope + peakX - (snowLineY - peakY) / leftSlope
        let rightX = peakX + (snowLineY - peakY) / rightSlope

        path.move(to: CGPoint(x: peakX - (snowLineY - peakY) / leftSlope, y: snowLineY))
        path.addLine(to: CGPoint(x: peakX, y: peakY))
        path.addLine(to: CGPoint(x: rightX, y: snowLineY))

        // Jagged snow line
        let steps = 8
        let stepWidth = (rightX - (peakX - (snowLineY - peakY) / leftSlope)) / CGFloat(steps)
        for i in stride(from: steps - 1, through: 0, by: -1) {
            let x = (peakX - (snowLineY - peakY) / leftSlope) + CGFloat(i) * stepWidth
            let yVariation = CGFloat.random(in: -5...5)
            path.addLine(to: CGPoint(x: x, y: snowLineY + yVariation))
        }

        path.closeSubpath()

        return path
    }
}

#Preview {
    SplashView()
}
