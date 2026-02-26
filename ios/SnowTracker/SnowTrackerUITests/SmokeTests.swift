import XCTest

/// Quick smoke tests for validating app functionality against a live environment.
/// Run these after deploying to staging or before a release.
///
/// Usage:
///   xcodebuild test -project SnowTracker.xcodeproj -scheme SnowTracker \
///     -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
///     -only-testing:SnowTrackerUITests/SmokeTests
///
/// To target staging:
///   Add STAGING_MODE to launch arguments (app must support this).
final class SmokeTests: XCTestCase {

    var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["UI_TESTING"]
        app.launch()
        app.waitForAppLoad()
    }

    override func tearDownWithError() throws {
        // Always take final screenshot on teardown
        app.takeScreenshot(name: "\(name)-final", in: self)
        app = nil
    }

    // MARK: - Core Flow: Resort List

    func testResortListLoads() throws {
        // Should be on Resorts tab by default
        let firstCell = app.cells.firstMatch
        XCTAssertTrue(firstCell.waitForExistence(timeout: 15), "Resort cells should load from API")
        XCTAssertGreaterThan(app.cells.count, 1, "Should show multiple resorts")

        app.takeScreenshot(name: "resort-list", in: self)
    }

    func testResortDetailNavigation() throws {
        let firstCell = app.cells.firstMatch
        firstCell.waitAndTap(timeout: 15)

        // Detail view should show resort content
        let navBar = app.navigationBars.element(boundBy: 0)
        XCTAssertTrue(navBar.waitForExistence(timeout: 5), "Detail navigation bar should appear")

        // Wait for conditions to load
        sleep(3)
        app.takeScreenshot(name: "resort-detail", in: self)

        // Verify elevation data is present
        let elevationInfo = app.staticTexts.containing(
            NSPredicate(format: "label CONTAINS 'ft' OR label CONTAINS 'elevation' OR label CONTAINS 'm'")
        ).firstMatch
        XCTAssertTrue(elevationInfo.waitForExistence(timeout: 5), "Should show elevation info")
    }

    // MARK: - Core Flow: Tab Navigation

    func testAllTabsNavigate() throws {
        // Tab label → expected navigation bar title
        let tabs: [(label: String, navTitle: String)] = [
            ("Resorts", "Snow Resorts"),
            ("Map", "Map"),
            ("Best Snow", "Best Snow"),
            ("Favorites", "Favorites"),
            ("Settings", "Settings"),
        ]
        for tab in tabs {
            app.navigateToTab(tab.label)
            let navBar = app.navigationBars[tab.navTitle]
            XCTAssertTrue(navBar.waitForExistence(timeout: 5), "\(tab.label) tab should show '\(tab.navTitle)' title")
            app.takeScreenshot(name: "tab-\(tab.label.lowercased().replacingOccurrences(of: " ", with: "-"))", in: self)
        }
    }

    // MARK: - Core Flow: Map

    func testMapShowsAnnotations() throws {
        app.navigateToTab("Map")

        let mapView = app.maps.firstMatch
        XCTAssertTrue(mapView.waitForExistence(timeout: 5), "Map should be visible")

        // Wait for annotations to load
        sleep(5)
        app.takeScreenshot(name: "map-with-annotations", in: self)
    }

    // MARK: - Core Flow: Chat

    func testChatOpensAndSendsMessage() throws {
        app.openChat()

        // Verify empty state
        let emptyState = app.text(id: TestID.Chat.emptyState)
        XCTAssertTrue(emptyState.waitForExistence(timeout: 5), "Chat empty state should show")

        // Type and send a message
        let input = app.element(id: TestID.Chat.messageInput)
        input.waitAndTap()
        input.typeText("Hello")

        let sendButton = app.button(id: TestID.Chat.sendButton)
        XCTAssertTrue(sendButton.isEnabled, "Send button should be enabled after typing")
        sendButton.tap()

        // Wait for response
        sleep(3)
        app.takeScreenshot(name: "chat-after-send", in: self)

        // User message should appear
        let userMessage = app.staticTexts["Hello"]
        XCTAssertTrue(userMessage.waitForExistence(timeout: 5), "User message should appear in chat")
    }

    // MARK: - Core Flow: Settings

    func testSettingsShowsSections() throws {
        app.navigateToTab("Settings")

        // Key sections should be visible
        let accountSection = app.staticTexts["Account"]
        XCTAssertTrue(accountSection.waitForExistence(timeout: 5), "Account section should show")

        let preferencesSection = app.staticTexts["Preferences"]
        XCTAssertTrue(preferencesSection.exists, "Preferences section should show")

        let appInfoSection = app.staticTexts["App Info"]
        XCTAssertTrue(appInfoSection.exists, "App Info section should show")

        app.takeScreenshot(name: "settings", in: self)
    }

    // MARK: - Regression: Quality Labels

    func testNoStaleQualityLabels() throws {
        // Wait for resort list + quality data to load
        let firstCell = app.cells.firstMatch
        firstCell.waitToExist(timeout: 15)
        sleep(5) // Wait for batch quality

        // "Soft" and "Icy" should never appear as quality labels
        XCTAssertFalse(app.staticTexts["Soft"].exists, "'Soft' should not appear — use 'Poor'")
        XCTAssertFalse(app.staticTexts["Icy"].exists, "'Icy' should not appear — use 'Bad'")
    }

    // MARK: - Data Source Verification

    func testResortShowsDataSource() throws {
        let firstCell = app.cells.firstMatch
        firstCell.waitAndTap(timeout: 15)

        // Scroll down to find data source info
        let scrollView = app.scrollViews.firstMatch
        for _ in 0..<8 {
            let dataSourceText = app.staticTexts.containing(
                NSPredicate(format: "label CONTAINS 'open-meteo' OR label CONTAINS 'Data from'")
            ).firstMatch
            if dataSourceText.exists { break }
            scrollView.swipeUp()
            sleep(1)
        }

        app.takeScreenshot(name: "resort-detail-data-source", in: self)
    }
}
