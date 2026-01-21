import XCTest

final class SnowTrackerUITests: XCTestCase {

    var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["UI_TESTING"]
        app.launch()
    }

    override func tearDownWithError() throws {
        app = nil
    }

    // MARK: - Tab Bar Tests

    func testTabBarExists() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 5))
    }

    func testTabBarHasAllTabs() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 5))

        // Check for expected tabs
        let resortsTab = tabBar.buttons["Resorts"]
        let conditionsTab = tabBar.buttons["Conditions"]
        let favoritesTab = tabBar.buttons["Favorites"]
        let settingsTab = tabBar.buttons["Settings"]

        XCTAssertTrue(resortsTab.exists)
        XCTAssertTrue(conditionsTab.exists)
        XCTAssertTrue(favoritesTab.exists)
        XCTAssertTrue(settingsTab.exists)
    }

    func testNavigateToConditionsTab() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 5))

        tabBar.buttons["Conditions"].tap()

        // Verify we're on the conditions screen by checking for navigation title
        let conditionsTitle = app.navigationBars["Snow Conditions"]
        XCTAssertTrue(conditionsTitle.waitForExistence(timeout: 3))
    }

    func testNavigateToFavoritesTab() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 5))

        tabBar.buttons["Favorites"].tap()

        // Verify we're on the favorites screen
        let favoritesTitle = app.navigationBars["Favorites"]
        XCTAssertTrue(favoritesTitle.waitForExistence(timeout: 3))
    }

    func testNavigateToSettingsTab() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 5))

        tabBar.buttons["Settings"].tap()

        // Verify we're on the settings screen
        let settingsTitle = app.navigationBars["Settings"]
        XCTAssertTrue(settingsTitle.waitForExistence(timeout: 3))
    }

    // MARK: - Resorts Screen Tests

    func testResortsScreenShowsTitle() throws {
        // Resorts tab should be selected by default
        let resortsTitle = app.navigationBars["Snow Resorts"]
        XCTAssertTrue(resortsTitle.waitForExistence(timeout: 5))
    }

    // MARK: - Settings Screen Tests

    func testSettingsScreenShowsAppInfo() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 5))

        tabBar.buttons["Settings"].tap()

        // Check for App Info section
        let appInfoHeader = app.staticTexts["App Info"]
        XCTAssertTrue(appInfoHeader.waitForExistence(timeout: 3))

        // Check for version info
        let versionLabel = app.staticTexts["App Version"]
        XCTAssertTrue(versionLabel.exists)
    }

    func testSettingsScreenShowsAccountSection() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 5))

        tabBar.buttons["Settings"].tap()

        // Check for Account section
        let accountHeader = app.staticTexts["Account"]
        XCTAssertTrue(accountHeader.waitForExistence(timeout: 3))
    }

    func testSettingsScreenShowsPreferencesSection() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 5))

        tabBar.buttons["Settings"].tap()

        // Check for Preferences section
        let preferencesHeader = app.staticTexts["Preferences"]
        XCTAssertTrue(preferencesHeader.waitForExistence(timeout: 3))

        // Check for Notifications link
        let notificationsLink = app.buttons["Notifications"]
        XCTAssertTrue(notificationsLink.exists)

        // Check for Units link
        let unitsLink = app.buttons["Units"]
        XCTAssertTrue(unitsLink.exists)
    }

    func testSettingsScreenShowsLegalSection() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 5))

        tabBar.buttons["Settings"].tap()

        // Scroll down to find Legal section (it might be off screen)
        app.swipeUp()

        // Check for Legal section
        let legalHeader = app.staticTexts["Legal"]
        XCTAssertTrue(legalHeader.waitForExistence(timeout: 3))
    }

    func testNavigateToNotificationSettings() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 5))

        tabBar.buttons["Settings"].tap()

        // Tap on Notifications
        let notificationsButton = app.buttons["Notifications"]
        XCTAssertTrue(notificationsButton.waitForExistence(timeout: 3))
        notificationsButton.tap()

        // Verify we're on the Notifications settings screen
        let notificationsTitle = app.navigationBars["Notifications"]
        XCTAssertTrue(notificationsTitle.waitForExistence(timeout: 3))
    }

    func testNavigateToUnitsSettings() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 5))

        tabBar.buttons["Settings"].tap()

        // Tap on Units
        let unitsButton = app.buttons["Units"]
        XCTAssertTrue(unitsButton.waitForExistence(timeout: 3))
        unitsButton.tap()

        // Verify we're on the Units settings screen
        let unitsTitle = app.navigationBars["Units"]
        XCTAssertTrue(unitsTitle.waitForExistence(timeout: 3))
    }

    // MARK: - Debug Settings Tests (Only in DEBUG builds)

    #if DEBUG
    func testSettingsScreenShowsDeveloperSettings() throws {
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 5))

        tabBar.buttons["Settings"].tap()

        // Check for Developer Settings section (only visible in DEBUG)
        let developerHeader = app.staticTexts["Developer Settings"]
        XCTAssertTrue(developerHeader.waitForExistence(timeout: 3))

        // Check for Use Custom API URL toggle
        let customAPIToggle = app.switches["Use Custom API URL"]
        XCTAssertTrue(customAPIToggle.exists)
    }
    #endif
}
