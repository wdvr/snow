import WidgetKit
import SwiftUI

@main
struct SnowTrackerWidgetBundle: WidgetBundle {
    var body: some Widget {
        FavoriteResortsWidget()
        BestResortsWidget()
    }
}
