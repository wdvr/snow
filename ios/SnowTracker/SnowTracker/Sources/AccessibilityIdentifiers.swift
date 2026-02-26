/// Stable accessibility identifiers for UI testing.
/// Used by both the app (`.accessibilityIdentifier()`) and UI tests (`app[.identifier]`).
///
/// Convention: `screen_element` format, e.g. `welcome_continueButton`.
enum AccessibilityID {
    // MARK: - Welcome / Auth
    enum Welcome {
        static let continueButton = "welcome_continueButton"
        static let appleSignInButton = "welcome_appleSignInButton"
        static let googleSignInButton = "welcome_googleSignInButton"
        static let appTitle = "welcome_appTitle"
        static let errorMessage = "welcome_errorMessage"
    }

    // MARK: - Main Tab Bar
    enum Tab {
        static let bar = "tab_bar"
        static let resorts = "tab_resorts"
        static let map = "tab_map"
        static let bestSnow = "tab_bestSnow"
        static let favorites = "tab_favorites"
        static let settings = "tab_settings"
        static let chatFAB = "tab_chatFAB"
    }

    // MARK: - Resort List
    enum ResortList {
        static let searchField = "resortList_searchField"
        static let resortCell = "resortList_cell_" // append resort id
        static let qualityBadge = "resortList_qualityBadge_" // append resort id
        static let regionFilter = "resortList_regionFilter"
        static let sortButton = "resortList_sortButton"
        static let offlineBanner = "resortList_offlineBanner"
    }

    // MARK: - Resort Detail
    enum ResortDetail {
        static let scrollView = "resortDetail_scrollView"
        static let qualityScore = "resortDetail_qualityScore"
        static let explanation = "resortDetail_explanation"
        static let elevationPicker = "resortDetail_elevationPicker"
        static let conditionsCard = "resortDetail_conditionsCard"
        static let forecastTimeline = "resortDetail_forecastTimeline"
        static let freshPowderChart = "resortDetail_freshPowderChart"
        static let snowHistoryChart = "resortDetail_snowHistoryChart"
        static let favoriteButton = "resortDetail_favoriteButton"
        static let shareButton = "resortDetail_shareButton"
        static let reportButton = "resortDetail_reportButton"
        static let dataSource = "resortDetail_dataSource"
    }

    // MARK: - Map
    enum Map {
        static let mapView = "map_mapView"
        static let regionButton = "map_regionButton"
        static let legendButton = "map_legendButton"
        static let legendPanel = "map_legendPanel"
        static let filterAll = "map_filterAll"
        static let annotation = "map_annotation_" // append resort id
    }

    // MARK: - Best Snow
    enum BestSnow {
        static let list = "bestSnow_list"
        static let resortCard = "bestSnow_card_" // append resort id
    }

    // MARK: - Favorites
    enum Favorites {
        static let list = "favorites_list"
        static let emptyState = "favorites_emptyState"
    }

    // MARK: - Settings
    enum Settings {
        static let list = "settings_list"
        static let accountSection = "settings_accountSection"
        static let preferencesSection = "settings_preferencesSection"
        static let notificationsButton = "settings_notificationsButton"
        static let unitsButton = "settings_unitsButton"
        static let appVersion = "settings_appVersion"
    }

    // MARK: - Chat
    enum Chat {
        static let messageInput = "chat_messageInput"
        static let sendButton = "chat_sendButton"
        static let historyButton = "chat_historyButton"
        static let newConversationButton = "chat_newConversationButton"
        static let emptyState = "chat_emptyState"
        static let suggestionChip = "chat_suggestionChip_" // append index
        static let messageBubble = "chat_message_" // append index
    }

    // MARK: - Condition Report
    enum ConditionReport {
        static let submitButton = "conditionReport_submitButton"
        static let conditionPicker = "conditionReport_conditionPicker"
    }

    // MARK: - Suggest Edit
    enum SuggestEdit {
        static let button = "suggestEdit_button"
        static let submitButton = "suggestEdit_submitButton"
    }

    // MARK: - Onboarding
    enum Onboarding {
        static let continueButton = "onboarding_continueButton"
        static let skipButton = "onboarding_skipButton"
    }
}
