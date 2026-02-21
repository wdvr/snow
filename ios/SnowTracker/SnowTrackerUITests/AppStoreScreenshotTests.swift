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

        let tabBar = ensureTabBar()
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15))

        sleep(5)

        takeScreenshot(name: "07-ipad-resorts-list")
    }

    func testScreenshot08_iPadMapView() throws {
        guard UIDevice.current.userInterfaceIdiom == .pad else {
            throw XCTSkip("iPad-only test")
        }

        let tabBar = ensureTabBar()
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15))

        tabBar.buttons["Map"].tap()
        sleep(5)

        takeScreenshot(name: "08-ipad-map-view")
    }

    func testScreenshot09_iPadResortDetail() throws {
        guard UIDevice.current.userInterfaceIdiom == .pad else {
            throw XCTSkip("iPad-only test")
        }

        let tabBar = ensureTabBar()
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15))

        tabBar.buttons["Resorts"].tap()
        sleep(3)

        let cells = app.cells
        if cells.count > 0 {
            cells.element(boundBy: 0).tap()
        }

        sleep(3)

        takeScreenshot(name: "09-ipad-resort-detail")
    }

    // MARK: - Special Feature Screenshots

    func testScreenshot10_SearchResults() throws {
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
            takeScreenshot(name: "10-search-results")
        }
    }

    func testScreenshot11_Favorites() throws {
        let tabBar = ensureTabBar()
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15))

        // Go to Favorites tab
        tabBar.buttons["Favorites"].tap()
        sleep(2)

        takeScreenshot(name: "11-favorites")
    }
}
