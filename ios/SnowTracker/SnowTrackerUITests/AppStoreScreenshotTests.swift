import XCTest

final class AppStoreScreenshotTests: XCTestCase {

    var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["UI_TESTING", "SCREENSHOT_MODE", "DEMO_DATA"]

        // Setup fastlane snapshot
        setupSnapshot(app)

        app.launch()

        // Wait for app to fully launch
        sleep(2)
    }

    override func tearDownWithError() throws {
        app = nil
    }

    // MARK: - Screenshot Helper

    private func takeScreenshot(name: String, delay: Double = 2.0) {
        sleep(UInt32(delay))
        snapshot(name)
    }

    // MARK: - iPhone Screenshots (Required sizes: 6.7", 6.5", 5.5")

    func testScreenshot01_SplashScreen() throws {
        // Capture the beautiful animated splash screen with falling snow
        let splashView = app.otherElements["SplashView"]
        XCTAssertTrue(splashView.waitForExistence(timeout: 5))

        takeScreenshot(name: "01-splash-screen", delay: 3.0)
    }

    func testScreenshot02_ResortsList() throws {
        // Wait for app to fully load past splash
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 10))

        // Ensure we're on Resorts tab (default)
        tabBar.buttons["Resorts"].tap()

        // Wait for resort data to load
        let bigWhite = app.staticTexts["Big White Ski Resort"]
        XCTAssertTrue(bigWhite.waitForExistence(timeout: 10))

        takeScreenshot(name: "02-resorts-list")
    }

    func testScreenshot03_ResortDetail() throws {
        // Navigate to resort detail
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 10))

        let bigWhite = app.staticTexts["Big White Ski Resort"]
        XCTAssertTrue(bigWhite.waitForExistence(timeout: 10))
        bigWhite.tap()

        // Wait for detail view to load completely
        let currentConditionsCard = app.staticTexts["Current Conditions"]
        XCTAssertTrue(currentConditionsCard.waitForExistence(timeout: 5))

        takeScreenshot(name: "03-resort-detail")
    }

    func testScreenshot04_MapViewWithNearby() throws {
        // Navigate back to main screen first
        if app.navigationBars.buttons["Back"].exists {
            app.navigationBars.buttons["Back"].tap()
        }

        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.exists)

        // Navigate to Map tab
        tabBar.buttons["Map"].tap()

        let mapView = app.maps.firstMatch
        XCTAssertTrue(mapView.waitForExistence(timeout: 5))

        // Wait for map pins to load
        sleep(3)

        // Show legend for better screenshot
        let infoButton = app.buttons["info.circle"]
        if infoButton.waitForExistence(timeout: 3) {
            infoButton.tap()
            sleep(1) // Let legend appear
        }

        takeScreenshot(name: "04-map-view-with-legend")
    }

    func testScreenshot05_ConditionsOverview() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.exists)

        // Navigate to Conditions tab
        tabBar.buttons["Conditions"].tap()

        // Wait for conditions to load
        let conditionsTitle = app.navigationBars["Snow Conditions"]
        XCTAssertTrue(conditionsTitle.waitForExistence(timeout: 5))

        // Wait for condition cards to populate
        sleep(2)

        takeScreenshot(name: "05-conditions-overview")
    }

    func testScreenshot06_Settings() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.exists)

        // Navigate to Settings tab
        tabBar.buttons["Settings"].tap()

        let settingsTitle = app.navigationBars["Settings"]
        XCTAssertTrue(settingsTitle.waitForExistence(timeout: 3))

        takeScreenshot(name: "06-settings")
    }

    // MARK: - iPad Screenshots (Required sizes: 12.9", 11")

    func testScreenshot07_iPadResortsList() throws {
        // Only run on iPad
        guard UIDevice.current.userInterfaceIdiom == .pad else {
            throw XCTSkip("iPad-only test")
        }

        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 10))

        let bigWhite = app.staticTexts["Big White Ski Resort"]
        XCTAssertTrue(bigWhite.waitForExistence(timeout: 10))

        takeScreenshot(name: "07-ipad-resorts-list")
    }

    func testScreenshot08_iPadMapView() throws {
        guard UIDevice.current.userInterfaceIdiom == .pad else {
            throw XCTSkip("iPad-only test")
        }

        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.exists)

        tabBar.buttons["Map"].tap()

        let mapView = app.maps.firstMatch
        XCTAssertTrue(mapView.waitForExistence(timeout: 5))

        sleep(3)

        takeScreenshot(name: "08-ipad-map-view")
    }

    func testScreenshot09_iPadResortDetail() throws {
        guard UIDevice.current.userInterfaceIdiom == .pad else {
            throw XCTSkip("iPad-only test")
        }

        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 10))

        tabBar.buttons["Resorts"].tap()

        let bigWhite = app.staticTexts["Big White Ski Resort"]
        XCTAssertTrue(bigWhite.waitForExistence(timeout: 10))
        bigWhite.tap()

        let currentConditionsCard = app.staticTexts["Current Conditions"]
        XCTAssertTrue(currentConditionsCard.waitForExistence(timeout: 5))

        takeScreenshot(name: "09-ipad-resort-detail")
    }

    // MARK: - Special Feature Screenshots

    func testScreenshot10_SearchResults() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 10))

        // Tap search field if available
        let searchField = app.searchFields.firstMatch
        if searchField.waitForExistence(timeout: 3) {
            searchField.tap()
            searchField.typeText("Big White")

            sleep(2) // Wait for search results

            takeScreenshot(name: "10-search-results")

            // Clear search
            if let clearButton = searchField.buttons["Clear text"].firstOrNil {
                clearButton.tap()
            }
        }
    }

    func testScreenshot11_RegionFilters() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 10))

        // Look for region filter chips
        let northAmericaFilter = app.buttons.matching(NSPredicate(format: "label CONTAINS 'North America'")).firstMatch
        if northAmericaFilter.waitForExistence(timeout: 3) {
            northAmericaFilter.tap()

            sleep(2)

            takeScreenshot(name: "11-region-filters")
        }
    }

    func testScreenshot12_FavoritesWithContent() throws {
        // First add a favorite
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 10))

        let bigWhite = app.staticTexts["Big White Ski Resort"]
        XCTAssertTrue(bigWhite.waitForExistence(timeout: 10))
        bigWhite.tap()

        // Add to favorites if heart button exists
        let favoriteButton = app.buttons["heart"]
        if favoriteButton.waitForExistence(timeout: 3) {
            favoriteButton.tap()
        }

        // Navigate back
        if app.navigationBars.buttons["Back"].exists {
            app.navigationBars.buttons["Back"].tap()
        }

        // Go to Favorites tab
        tabBar.buttons["Favorites"].tap()

        sleep(2)

        takeScreenshot(name: "12-favorites-with-content")
    }
}

// MARK: - Helper Extensions

extension XCUIElementQuery {
    var firstOrNil: XCUIElement? {
        return count > 0 ? element(boundBy: 0) : nil
    }
}
