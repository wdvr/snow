import XCTest

// MARK: - Accessibility ID Constants (mirror app's AccessibilityID)
// These are duplicated as strings so UITests don't need to link the app target.

enum TestID {
    enum Welcome {
        static let continueButton = "welcome_continueButton"
        static let appTitle = "welcome_appTitle"
    }

    enum Tab {
        static let chatFAB = "tab_chatFAB"
    }

    enum ResortList {
        static let searchField = "resortList_searchField"
        static func cell(_ resortId: String) -> String { "resortList_cell_\(resortId)" }
    }

    enum ResortDetail {
        static let scrollView = "resortDetail_scrollView"
        static let qualityScore = "resortDetail_qualityScore"
        static let explanation = "resortDetail_explanation"
        static let favoriteButton = "resortDetail_favoriteButton"
        static let shareButton = "resortDetail_shareButton"
        static let reportButton = "resortDetail_reportButton"
        static let dataSource = "resortDetail_dataSource"
    }

    enum Map {
        static let mapView = "map_mapView"
        static let regionButton = "map_regionButton"
        static let legendButton = "map_legendButton"
    }

    enum Chat {
        static let messageInput = "chat_messageInput"
        static let sendButton = "chat_sendButton"
        static let historyButton = "chat_historyButton"
        static let newConversationButton = "chat_newConversationButton"
        static let emptyState = "chat_emptyState"
    }

    enum Settings {
        static let notificationsButton = "settings_notificationsButton"
        static let unitsButton = "settings_unitsButton"
    }

    enum ConditionReport {
        static let submitButton = "conditionReport_submitButton"
    }
}

// MARK: - XCUIApplication Helpers

extension XCUIApplication {
    /// Find element by accessibility identifier.
    func element(id: String) -> XCUIElement {
        descendants(matching: .any).matching(identifier: id).firstMatch
    }

    /// Find button by accessibility identifier.
    func button(id: String) -> XCUIElement {
        buttons.matching(identifier: id).firstMatch
    }

    /// Find static text by accessibility identifier.
    func text(id: String) -> XCUIElement {
        staticTexts.matching(identifier: id).firstMatch
    }
}

// MARK: - XCUIElement Helpers

extension XCUIElement {
    /// Wait for element to exist and return it (for chaining).
    @discardableResult
    func waitToExist(timeout: TimeInterval = 10, file: StaticString = #file, line: UInt = #line) -> XCUIElement {
        let exists = waitForExistence(timeout: timeout)
        XCTAssertTrue(exists, "Element '\(identifier)' did not appear within \(timeout)s", file: file, line: line)
        return self
    }

    /// Wait for element to exist, then tap it.
    func waitAndTap(timeout: TimeInterval = 10, file: StaticString = #file, line: UInt = #line) {
        waitToExist(timeout: timeout, file: file, line: line)
        tap()
    }
}

// MARK: - Common Navigation Helpers

extension XCUIApplication {
    /// Navigate to a specific tab by label.
    func navigateToTab(_ label: String) {
        let tab = tabBars.firstMatch.buttons[label]
        tab.waitAndTap(timeout: 10)
    }

    /// Wait for the app to fully load (tab bar visible).
    func waitForAppLoad(timeout: TimeInterval = 15) {
        let tabBar = tabBars.firstMatch
        XCTAssertTrue(tabBar.waitForExistence(timeout: timeout), "App should load and show tab bar")
    }

    /// Open the AI chat via the floating action button.
    func openChat() {
        button(id: TestID.Tab.chatFAB).waitAndTap()
        // Wait for chat navigation bar
        navigationBars["Ask AI"].waitToExist()
    }

    /// Take a named screenshot and attach it to the test.
    func takeScreenshot(name: String, in testCase: XCTestCase, lifetime: XCTAttachment.Lifetime = .keepAlways) {
        let screenshot = XCTAttachment(screenshot: self.screenshot())
        screenshot.name = name
        screenshot.lifetime = lifetime
        testCase.add(screenshot)
    }
}
