//
//  SnapshotHelper.swift
//  SnowTrackerUITests
//
//  Fastlane Snapshot Helper for automated App Store screenshot generation
//

import Foundation
import XCTest

var deviceLanguage = ""
var locale = ""

func setupSnapshot(_ app: XCUIApplication, waitForAnimations: Bool = true) {
    Snapshot.setupSnapshot(app, waitForAnimations: waitForAnimations)
}

func snapshot(_ name: String, timeWaitingForIdle timeout: TimeInterval = 20) {
    Snapshot.snapshot(name, timeWaitingForIdle: timeout)
}

enum SnapshotError: Error, CustomDebugStringConvertible {
    case cannotDetectUser
    case cannotFindSimulatorHomeDirectory
    case cannotFindSnapshotDirectory
    case cannotRunOnPhysicalDevice

    var debugDescription: String {
        switch self {
        case .cannotDetectUser:
            return "Couldn't find Snapshot configuration files - can't detect current user"
        case .cannotFindSimulatorHomeDirectory:
            return "Couldn't find simulator home location. Please, check SIMULATOR_HOST_HOME env variable."
        case .cannotFindSnapshotDirectory:
            return "Couldn't find snapshot directory"
        case .cannotRunOnPhysicalDevice:
            return "Can't use Snapshot on a physical device."
        }
    }
}

@objcMembers
open class Snapshot: NSObject {
    static var app: XCUIApplication?
    static var waitForAnimations = true

    open class func setupSnapshot(_ app: XCUIApplication, waitForAnimations: Bool = true) {
        Snapshot.app = app
        Snapshot.waitForAnimations = waitForAnimations

        do {
            let launchArguments = try Snapshot.findSnapshotConfigurationFile()
            app.launchArguments += launchArguments
        } catch {
            print("⚠️ Snapshot configuration not found, using defaults")
        }

        if waitForAnimations {
            app.launchArguments += ["-UIApplication.disableCoreAnimations", "true"]
        }
    }

    class func findSnapshotConfigurationFile() throws -> [String] {
        guard let simulatorHostHome = ProcessInfo.processInfo.environment["SIMULATOR_HOST_HOME"] ?? ProcessInfo.processInfo.environment["HOME"] else {
            throw SnapshotError.cannotFindSimulatorHomeDirectory
        }

        let snapshotConfigPath = URL(fileURLWithPath: simulatorHostHome)
            .appendingPathComponent("Library")
            .appendingPathComponent("Caches")
            .appendingPathComponent("tools.fastlane")
            .appendingPathComponent("snapshot")
            .appendingPathComponent("snapshot-launch_arguments.txt")

        if FileManager.default.fileExists(atPath: snapshotConfigPath.path) {
            let content = try String(contentsOf: snapshotConfigPath, encoding: .utf8)
            return content.components(separatedBy: "\n").filter { !$0.isEmpty }
        }

        return []
    }

    open class func snapshot(_ name: String, timeWaitingForIdle timeout: TimeInterval = 20) {
        if timeout > 0 {
            waitForLoadingIndicatorToDisappear(within: timeout)
        }

        print("📷 Snapshot: \(name)")

        sleep(1)
        let screenshot = XCUIScreen.main.screenshot()

        guard var simulator = ProcessInfo.processInfo.environment["SIMULATOR_DEVICE_NAME"] else {
            print("⚠️ Couldn't detect simulator, saving to default location")
            saveScreenshot(screenshot, name: name, directory: "screenshots")
            return
        }

        simulator = simulator.trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: " ", with: "-")
            .replacingOccurrences(of: "(", with: "")
            .replacingOccurrences(of: ")", with: "")

        let language = ProcessInfo.processInfo.environment["FASTLANE_SNAPSHOT_LANGUAGES"] ?? "en-US"
        let screenshotDir = "\(screenshotPath())/\(language)/\(simulator)"

        saveScreenshot(screenshot, name: name, directory: screenshotDir)
    }

    private class func saveScreenshot(_ screenshot: XCUIScreenshot, name: String, directory: String) {
        do {
            try FileManager.default.createDirectory(atPath: directory, withIntermediateDirectories: true)
            let screenshotPath = "\(directory)/\(name).png"
            try screenshot.pngRepresentation.write(to: URL(fileURLWithPath: screenshotPath))
            print("📱 Saved screenshot at \(screenshotPath)")
        } catch {
            print("❌ Problem saving screenshot: \(error)")
        }
    }

    class func waitForLoadingIndicatorToDisappear(within timeout: TimeInterval) {
        guard let app = self.app else { return }

        let networkLoadingIndicator = app.statusBars.otherElements.matching(identifier: "In Call").element
        let loadingIndicator = app.activityIndicators.element

        let startTime = Date()
        while Date().timeIntervalSince(startTime) < timeout {
            if !networkLoadingIndicator.exists && !loadingIndicator.exists {
                break
            }
            Thread.sleep(forTimeInterval: 0.5)
        }
    }

    class func screenshotPath() -> String {
        if let outputDir = ProcessInfo.processInfo.environment["FASTLANE_SNAPSHOT_OUTPUT_DIRECTORY"] {
            return outputDir
        }
        return "./fastlane/screenshots"
    }
}
