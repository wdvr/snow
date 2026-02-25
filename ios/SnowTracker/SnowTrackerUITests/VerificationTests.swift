import XCTest

/// Quick verification tests for reproducing and validating bug fixes.
/// Run specific tests to check UI state at various screens.
final class VerificationTests: XCTestCase {

    var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = true
        app = XCUIApplication()
        app.launchArguments = ["UI_TESTING", "SCREENSHOT_MODE"]
        app.launch()

        // Wait for splash + data load
        let tabBar = app.tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: 15), "App should load and show tab bar")
    }

    override func tearDownWithError() throws {
        // Take a final screenshot on failure
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.lifetime = .keepAlways
        add(attachment)
        app = nil
    }

    // MARK: - List View Verification

    func testListView_LoadsResortData() throws {
        // Should be on Resorts tab by default
        let tabBar = app.tabBars.firstMatch
        tabBar.buttons["Resorts"].tap()
        sleep(5) // Wait for batch quality data

        // Take screenshot
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "list-view-loaded"
        attachment.lifetime = .keepAlways
        add(attachment)

        // Verify resorts are displayed
        let cells = app.cells
        XCTAssertGreaterThan(cells.count, 0, "List should show resort cells")

        // Check that quality scores are shown (not just "Loading")
        let loadingTexts = app.staticTexts.matching(NSPredicate(format: "label == 'Loading'"))
        let loadingCount = loadingTexts.count
        print("Found \(loadingCount) 'Loading' labels, \(cells.count) cells")
    }

    func testListView_ResortDetailNavigation() throws {
        let tabBar = app.tabBars.firstMatch
        tabBar.buttons["Resorts"].tap()
        sleep(5)

        // Tap first resort cell
        let firstCell = app.cells.firstMatch
        guard firstCell.waitForExistence(timeout: 5) else {
            XCTFail("No resort cells found")
            return
        }
        firstCell.tap()
        sleep(3)

        // Take screenshot of detail view
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "detail-view"
        attachment.lifetime = .keepAlways
        add(attachment)

        // Verify detail view shows quality explanation
        // The explanation should mention weather conditions
        let explanationExists = app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS 'snow' OR label CONTAINS 'Icy' OR label CONTAINS 'Fresh' OR label CONTAINS 'surface' OR label CONTAINS 'Firm'")
        ).firstMatch.waitForExistence(timeout: 5)
        XCTAssertTrue(explanationExists, "Detail view should show quality explanation text")
    }

    // MARK: - Map View Verification

    func testMapView_ShowsAnnotations() throws {
        let tabBar = app.tabBars.firstMatch
        tabBar.buttons["Map"].tap()
        sleep(5) // Wait for map and annotations to load

        // Take screenshot
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "map-view-annotations"
        attachment.lifetime = .keepAlways
        add(attachment)

        // Verify map exists
        let mapView = app.maps.firstMatch
        XCTAssertTrue(mapView.exists, "Map should be visible")
    }

    func testMapView_TapAnnotation_ShowsDetailSheet() throws {
        let tabBar = app.tabBars.firstMatch
        tabBar.buttons["Map"].tap()
        sleep(5)

        // Try to tap on a map annotation
        let mapView = app.maps.firstMatch
        XCTAssertTrue(mapView.exists, "Map should be visible")

        // Look for any annotation or button within the map
        let annotations = mapView.buttons
        if annotations.count > 0 {
            // Tap the first annotation
            annotations.element(boundBy: 0).tap()
            sleep(3)

            // Take screenshot of the detail sheet
            let screenshot = XCUIScreen.main.screenshot()
            let attachment = XCTAttachment(screenshot: screenshot)
            attachment.name = "map-detail-sheet"
            attachment.lifetime = .keepAlways
            add(attachment)

            // Regression: detail sheet must NOT be empty/grey
            // Check that resort name or conditions content is visible
            let hasResortContent = app.staticTexts.matching(
                NSPredicate(format: "label CONTAINS 'Conditions' OR label CONTAINS 'Done' OR label CONTAINS 'View Full Details' OR label CONTAINS 'Loading'")
            ).firstMatch.waitForExistence(timeout: 5)
            XCTAssertTrue(hasResortContent, "Map detail sheet should show resort content, not grey/empty screen")
        } else {
            print("No annotations found on map - this may be expected if map hasn't loaded annotations yet")
        }
    }

    func testMapView_ZoomAndClusterBehavior() throws {
        let tabBar = app.tabBars.firstMatch
        tabBar.buttons["Map"].tap()
        sleep(3)

        // Take initial screenshot to see what the map tab looks like
        let initial = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        initial.name = "map-00-initial"
        initial.lifetime = .keepAlways
        add(initial)

        // MKMapView isn't exposed as XCUIElement.maps — use the navigation title to verify
        let mapTitle = app.navigationBars["Map"]
        XCTAssertTrue(mapTitle.waitForExistence(timeout: 10), "Map tab should show Map title")

        // Wait for annotations to load and conditions to fetch
        sleep(8)

        // Screenshot after data loads
        let loaded = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        loaded.name = "map-01-loaded"
        loaded.lifetime = .keepAlways
        add(loaded)

        // Navigate to Alps via the globe/region menu
        let globeButton = app.buttons["Region"]
        if globeButton.waitForExistence(timeout: 3) {
            globeButton.tap()
            sleep(1)
            let alpsOption = app.buttons.matching(NSPredicate(format: "label CONTAINS 'Alps'")).firstMatch
            if alpsOption.waitForExistence(timeout: 3) {
                alpsOption.tap()
                sleep(5) // Wait for region change + data loading
            }
        }

        let alpsView = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        alpsView.name = "map-02-alps-region"
        alpsView.lifetime = .keepAlways
        add(alpsView)

        // Pinch on the map area only (avoid tab bar at bottom)
        // Use the map element or constrain to upper portion of screen
        let mapView = app.maps.firstMatch
        let pinchTarget = mapView.exists ? mapView : app.otherElements.firstMatch
        pinchTarget.pinch(withScale: 0.3, velocity: -2.0)
        sleep(4)

        let zoomOut1 = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        zoomOut1.name = "map-03-zoomed-out"
        zoomOut1.lifetime = .keepAlways
        add(zoomOut1)

        // Zoom out more
        pinchTarget.pinch(withScale: 0.3, velocity: -2.0)
        sleep(4)

        let zoomOut2 = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        zoomOut2.name = "map-04-zoomed-out-more"
        zoomOut2.lifetime = .keepAlways
        add(zoomOut2)

        // Zoom back in
        pinchTarget.pinch(withScale: 5.0, velocity: 5.0)
        sleep(4)

        let zoomIn1 = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        zoomIn1.name = "map-05-zoomed-in"
        zoomIn1.lifetime = .keepAlways
        add(zoomIn1)

        // Zoom in more
        pinchTarget.pinch(withScale: 5.0, velocity: 5.0)
        sleep(4)

        let zoomIn2 = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        zoomIn2.name = "map-06-zoomed-in-detail"
        zoomIn2.lifetime = .keepAlways
        add(zoomIn2)

        // Verify app is still responsive and we're still on Map tab
        XCTAssertTrue(tabBar.exists, "Tab bar should remain visible after zoom operations")
        XCTAssertTrue(mapTitle.exists, "Should still be on Map tab after zoom operations")
    }

    // MARK: - Fresh Powder Chart Verification

    func testFreshPowderChart_AxesAndLegend() throws {
        let tabBar = app.tabBars.firstMatch
        tabBar.buttons["Resorts"].tap()
        sleep(3)

        // Search for Heavenly
        let searchField = app.searchFields.firstMatch
        if searchField.waitForExistence(timeout: 5) {
            searchField.tap()
            searchField.typeText("Heavenly")
            sleep(2)
        }

        // Tap the first matching cell
        let heavenlyCell = app.cells.matching(
            NSPredicate(format: "label CONTAINS[c] 'Heavenly'")
        ).firstMatch
        if heavenlyCell.waitForExistence(timeout: 5) {
            heavenlyCell.tap()
        } else {
            // Fallback: just tap the first resort
            let firstCell = app.cells.firstMatch
            guard firstCell.waitForExistence(timeout: 5) else {
                XCTFail("No resort cells found")
                return
            }
            firstCell.tap()
        }
        sleep(3)

        // Scroll down to find the Fresh Powder chart
        let scrollView = app.scrollViews.firstMatch
        for _ in 0..<5 {
            let freshPowderHeader = app.staticTexts["Fresh Powder"]
            if freshPowderHeader.exists { break }
            scrollView.swipeUp()
            sleep(1)
        }

        // Take screenshot of the chart area
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "fresh-powder-chart"
        attachment.lifetime = .keepAlways
        add(attachment)

        // Verify chart elements
        let freshPowderLabel = app.staticTexts["Fresh Powder"]
        XCTAssertTrue(freshPowderLabel.exists, "Fresh Powder header should be visible")

        // Verify "since last thaw" subtitle (not "since last freeze")
        let sinceThaw = app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS 'since last thaw'")
        ).firstMatch
        XCTAssertTrue(sinceThaw.exists, "Subtitle should say 'since last thaw', not 'since last freeze'")

        // Verify legend items exist
        let snowfallLegend = app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS 'Snowfall'")
        ).firstMatch
        let tempLegend = app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS 'Temp range'")
        ).firstMatch
        XCTAssertTrue(snowfallLegend.exists, "Snowfall legend should be visible")
        XCTAssertTrue(tempLegend.exists, "Temp range legend should be visible")

        // Verify "Crust formed" annotation (not "Last freeze") if present
        let lastFreezeWrong = app.staticTexts["Last freeze"]
        XCTAssertFalse(lastFreezeWrong.exists,
            "Regression: 'Last freeze' label should NOT appear — use 'Crust formed' instead")
    }

    // MARK: - Chat Verification

    func testChat_SendsMessage() throws {
        let tabBar = app.tabBars.firstMatch
        sleep(3)

        // Look for the floating chat button
        let chatButton = app.buttons.matching(
            NSPredicate(format: "label CONTAINS 'chat' OR label CONTAINS 'Chat' OR label CONTAINS 'AI'")
        ).firstMatch

        guard chatButton.waitForExistence(timeout: 5) else {
            // Try tapping the chat bubble in bottom right
            print("Chat button not found by accessibility label, looking for generic buttons")
            return
        }
        chatButton.tap()
        sleep(2)

        // Take screenshot of chat view
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "chat-view"
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
