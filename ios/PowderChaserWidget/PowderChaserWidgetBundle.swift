import WidgetKit
import SwiftUI

@main
struct PowderChaserWidgetBundle: WidgetBundle {
    var body: some Widget {
        FavoriteResortsWidget()
        BestResortsWidget()
        SnowLiveActivity()
    }
}
