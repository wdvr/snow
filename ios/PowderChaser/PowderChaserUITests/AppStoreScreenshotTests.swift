import XCTest

@MainActor
final class AppStoreScreenshotTests: XCTestCase {

    nonisolated(unsafe) var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["UI_TESTING", "SCREENSHOT_MODE", "DEMO_DATA"]

        // Setup fastlane snapshot
        setupSnapshot(app)

        app.launch()

        // Wait for splash screen to dismiss and app to fully load
        sleep(4)
    }

    override func tearDownWithError() throws {
        app = nil
    }

    // MARK: - Screenshot Helper

    private func takeScreenshot(name: String, delay: Double = 2.0) {
        sleep(UInt32(delay))
        snapshot(name)
    }

    private func ensureTabBar() -> XCUIElement {
        let tabBar = app.tabBars.firstMatch
        // If tab bar isn't visible, we may still be on splash/auth — wait longer
        if !tabBar.waitForExistence(timeout: 15) {
            // Try tapping "Continue without signing in" as fallback
            let continueButton = app.buttons["Continue without signing in"]
            if continueButton.exists {
                continueButton.tap()
                sleep(3)
            }
        }
        return tabBar
    }

    /// Wait for app content to load (works on both iPhone and iPad).
    /// On iPad (iOS 18+), TabView renders as a top bar that may not
    /// appear in app.tabBars, so we check for known tab buttons instead.
    private func ensureAppLoaded() {
        let tabBar = app.tabBars.firstMatch
        if tabBar.waitForExistence(timeout: 15) { return }

        // iPad fallback: look for tab buttons directly
        let resortsButton = app.buttons["Resorts"]
        if resortsButton.waitForExistence(timeout: 10) { return }

        // Last resort: try to tap through auth
        let continueButton = app.buttons["Continue without signing in"]
        if continueButton.exists {
            continueButton.tap()
            sleep(3)
        }
    }

    /// Navigate to a tab by name (works on both iPhone and iPad)
    private func selectTab(_ name: String) {
        // Try tab bar first (iPhone)
        let tabBar = app.tabBars.firstMatch
        if tabBar.exists {
            tabBar.buttons[name].tap()
            return
        }
        // iPad (iOS 18+): tab items are in a tabBar-like container
        // Use the first matching button to avoid ambiguity with other UI elements
        let buttons = app.buttons.matching(identifier: name)
        if buttons.count > 0 {
            buttons.element(boundBy: 0).tap()
        }
    }

    // MARK: - iPhone Screenshots (Required sizes: 6.9", 6.7", 6.5")

    func testScreenshot01_SplashScreen() throws {
        // Re-launch to catch splash screen
        app.terminate()
        app.launch()
        sleep(1) // Capture splash before it fades

        snapshot("01-splash-screen")
    }

    func testScreenshot02_ResortsList() throws {
        let tabBar = ensureTabBar()
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15))

        // Ensure we're on Resorts tab (default)
        tabBar.buttons["Resorts"].tap()

        // Wait for resort data to load
        sleep(5)

        takeScreenshot(name: "02-resorts-list")
    }

    func testScreenshot03_ResortDetail() throws {
        let tabBar = ensureTabBar()
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15))

        tabBar.buttons["Resorts"].tap()
        sleep(3)

        // Tap the first resort cell we can find
        let cells = app.cells
        if cells.count > 0 {
            cells.element(boundBy: 0).tap()
        }

        // Wait for detail view to load
        sleep(3)

        takeScreenshot(name: "03-resort-detail")
    }

    func testScreenshot04_MapView() throws {
        let tabBar = ensureTabBar()
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15))

        // Navigate to Map tab
        tabBar.buttons["Map"].tap()

        // Wait for map pins to load
        sleep(5)

        takeScreenshot(name: "04-map-view")
    }

    func testScreenshot05_BestSnow() throws {
        let tabBar = ensureTabBar()
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15))

        // Navigate to Best Snow tab
        tabBar.buttons["Best Snow"].tap()

        // Wait for recommendations to load
        sleep(5)

        takeScreenshot(name: "05-best-snow")
    }

    func testScreenshot06_Settings() throws {
        let tabBar = ensureTabBar()
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15))

        // Navigate to Settings tab
        tabBar.buttons["Settings"].tap()

        sleep(2)

        takeScreenshot(name: "06-settings")
    }

    // MARK: - iPad Screenshots (Required sizes: 12.9", 11")

    func testScreenshot07_iPadResortsList() throws {
        guard UIDevice.current.userInterfaceIdiom == .pad else {
            throw XCTSkip("iPad-only test")
        }

        ensureAppLoaded()
        sleep(5)

        takeScreenshot(name: "07-ipad-resorts-list")
    }

    func testScreenshot08_iPadMapView() throws {
        guard UIDevice.current.userInterfaceIdiom == .pad else {
            throw XCTSkip("iPad-only test")
        }

        ensureAppLoaded()
        selectTab("Map")
        sleep(5)

        takeScreenshot(name: "08-ipad-map-view")
    }

    func testScreenshot09_iPadResortDetail() throws {
        guard UIDevice.current.userInterfaceIdiom == .pad else {
            throw XCTSkip("iPad-only test")
        }

        ensureAppLoaded()
        selectTab("Resorts")
        sleep(3)

        let cells = app.cells
        if cells.count > 0 {
            cells.element(boundBy: 0).tap()
        }

        sleep(3)

        takeScreenshot(name: "09-ipad-resort-detail")
    }

    // MARK: - AI Chat Screenshots

    func testScreenshot10_AIChat() throws {
        let tabBar = ensureTabBar()
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15))

        // Tap the floating AI chat button
        let chatFAB = app.buttons["tab_chatFAB"]
        if chatFAB.waitForExistence(timeout: 5) {
            chatFAB.tap()
            sleep(2)

            // Type a question to show the chat interface
            let textField = app.textFields.firstMatch
            if textField.waitForExistence(timeout: 5) {
                textField.tap()
                textField.typeText("Where's the best powder right now?")
                sleep(1)
            }

            takeScreenshot(name: "10-ai-chat")
        }
    }

    func testScreenshot11_AIChatIPad() throws {
        guard UIDevice.current.userInterfaceIdiom == .pad else {
            throw XCTSkip("iPad-only test")
        }

        ensureAppLoaded()

        let chatFAB = app.buttons["tab_chatFAB"]
        if chatFAB.waitForExistence(timeout: 5) {
            chatFAB.tap()
            sleep(2)

            let textField = app.textFields.firstMatch
            if textField.waitForExistence(timeout: 5) {
                textField.tap()
                textField.typeText("Where's the best powder right now?")
                sleep(1)
            }

            takeScreenshot(name: "11-ipad-ai-chat")
        }
    }

    // MARK: - Special Feature Screenshots

    func testScreenshot12_SearchResults() throws {
        let tabBar = ensureTabBar()
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15))

        tabBar.buttons["Resorts"].tap()
        sleep(2)

        // Tap search field if available
        let searchField = app.searchFields.firstMatch
        if searchField.waitForExistence(timeout: 5) {
            searchField.tap()
            searchField.typeText("Chamonix")
            sleep(2)
            takeScreenshot(name: "12-search-results")
        }
    }

    func testScreenshot14_MapResortDetail() throws {
        let tabBar = ensureTabBar()
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15))

        // Go to Resorts tab
        tabBar.buttons["Resorts"].tap()
        sleep(3)

        // Scroll down to find resorts further in the list (more interesting data)
        let listScroll = app.scrollViews.firstMatch
        if listScroll.exists {
            listScroll.swipeUp()
            sleep(1)
            listScroll.swipeUp()
            sleep(1)
        }

        // Tap a resort from this section
        let cells = app.cells
        if cells.count > 0 {
            // Pick a resort visible after scrolling (shows trail map, run difficulty etc.)
            let index = min(3, cells.count - 1)
            cells.element(boundBy: index).tap()
            sleep(3)
        }

        takeScreenshot(name: "14-resort-detail-scroll")
    }

    func testScreenshot13_Favorites() throws {
        let tabBar = ensureTabBar()
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15))

        // Go to Favorites tab
        tabBar.buttons["Favorites"].tap()
        sleep(2)

        takeScreenshot(name: "13-favorites")
    }
}
