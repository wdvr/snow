// swift-tools-version: 6.0
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "SnowTracker",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    products: [
        .library(
            name: "SnowTracker",
            targets: ["SnowTracker"]
        )
    ],
    dependencies: [
        // Core dependencies for networking and data handling
        .package(url: "https://github.com/Alamofire/Alamofire.git", from: "5.8.0"),

        // Authentication with Apple
        .package(url: "https://github.com/firebase/firebase-ios-sdk.git", from: "10.20.0"),

        // JSON handling and API client generation
        .package(url: "https://github.com/CreateAPI/Get.git", from: "2.1.0"),

        // Async image loading
        .package(url: "https://github.com/kean/Nuke.git", from: "12.1.0"),

        // Keychain access for secure storage
        .package(url: "https://github.com/evgenyneu/keychain-swift.git", from: "20.0.0"),

        // Testing utilities
        .package(url: "https://github.com/pointfreeco/swift-snapshot-testing.git", from: "1.15.0")
    ],
    targets: [
        .target(
            name: "SnowTracker",
            dependencies: [
                "Alamofire",
                .product(name: "FirebaseAuth", package: "firebase-ios-sdk"),
                "Get",
                "Nuke",
                .product(name: "KeychainSwift", package: "keychain-swift")
            ]
        ),
        .testTarget(
            name: "SnowTrackerTests",
            dependencies: [
                "SnowTracker",
                .product(name: "SnapshotTesting", package: "swift-snapshot-testing")
            ]
        )
    ]
)
