package com.powderchaserapp.android.ui.navigation

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.powderchaserapp.android.R
import com.powderchaserapp.android.service.NetworkMonitor
import com.powderchaserapp.android.ui.components.OfflineBanner
import com.powderchaserapp.android.ui.screens.bestsnow.BestSnowScreen
import com.powderchaserapp.android.ui.screens.chat.ChatScreen
import com.powderchaserapp.android.ui.screens.comparison.ComparisonScreen
import com.powderchaserapp.android.ui.screens.conditionreport.ConditionReportScreen
import com.powderchaserapp.android.ui.screens.favorites.FavoritesScreen
import com.powderchaserapp.android.ui.screens.notifications.NotificationSettingsScreen
import com.powderchaserapp.android.ui.screens.onboarding.OnboardingScreen
import com.powderchaserapp.android.ui.screens.resortdetail.ResortDetailScreen
import com.powderchaserapp.android.ui.screens.resortlist.ResortListScreen
import com.powderchaserapp.android.ui.screens.resortmap.ResortMapScreen
import com.powderchaserapp.android.ui.screens.settings.SettingsScreen
import com.powderchaserapp.android.ui.screens.splash.SplashScreen
import com.powderchaserapp.android.ui.screens.trips.TripListScreen
import com.powderchaserapp.android.ui.screens.welcome.WelcomeScreen

// Route definitions
object Routes {
    const val SPLASH = "splash"
    const val WELCOME = "welcome"
    const val ONBOARDING = "onboarding"
    const val RESORT_LIST = "resorts"
    const val RESORT_DETAIL = "resorts/{resortId}"
    const val RESORT_MAP = "map"
    const val BEST_SNOW = "best_snow"
    const val FAVORITES = "favorites"
    const val SETTINGS = "settings"
    const val CHAT = "chat"
    const val TRIPS = "trips"
    const val COMPARISON = "comparison"
    const val CONDITION_REPORT = "condition_report/{resortId}"
    const val NOTIFICATION_SETTINGS = "notification_settings"

    fun resortDetail(resortId: String) = "resorts/$resortId"
    fun conditionReport(resortId: String) = "condition_report/$resortId"
}

// Bottom navigation items
sealed class BottomNavItem(
    val route: String,
    val icon: ImageVector,
    val labelResId: Int,
) {
    data object Resorts : BottomNavItem(Routes.RESORT_LIST, Icons.Default.Terrain, R.string.tab_resorts)
    data object Map : BottomNavItem(Routes.RESORT_MAP, Icons.Default.Map, R.string.tab_map)
    data object BestSnow : BottomNavItem(Routes.BEST_SNOW, Icons.Default.Stars, R.string.tab_best_snow)
    data object Favorites : BottomNavItem(Routes.FAVORITES, Icons.Default.Favorite, R.string.tab_favorites)
    data object Settings : BottomNavItem(Routes.SETTINGS, Icons.Default.Settings, R.string.tab_settings)
}

val bottomNavItems = listOf(
    BottomNavItem.Resorts,
    BottomNavItem.Map,
    BottomNavItem.BestSnow,
    BottomNavItem.Favorites,
    BottomNavItem.Settings,
)

@Composable
fun PowderChaserNavHost(
    networkMonitor: NetworkMonitor,
    navController: NavHostController = rememberNavController(),
    startDestination: String = Routes.SPLASH,
) {
    @OptIn(ExperimentalMaterial3Api::class)
    Scaffold(
        bottomBar = {
            val navBackStackEntry by navController.currentBackStackEntryAsState()
            val currentDestination = navBackStackEntry?.destination
            val showBottomBar = bottomNavItems.any { item ->
                currentDestination?.hierarchy?.any { it.route == item.route } == true
            }

            if (showBottomBar) {
                NavigationBar {
                    bottomNavItems.forEach { item ->
                        NavigationBarItem(
                            icon = { Icon(item.icon, contentDescription = stringResource(item.labelResId)) },
                            label = { Text(stringResource(item.labelResId)) },
                            selected = currentDestination?.hierarchy?.any {
                                it.route == item.route
                            } == true,
                            onClick = {
                                navController.navigate(item.route) {
                                    popUpTo(navController.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                        )
                    }
                }
            }
        },
    ) { innerPadding ->
        Column(modifier = Modifier.padding(innerPadding)) {
            // Offline banner at top
            OfflineBanner(networkMonitor = networkMonitor)

            NavHost(
                navController = navController,
                startDestination = startDestination,
            ) {
                composable(Routes.SPLASH) {
                    SplashScreen(
                        onNavigateToWelcome = {
                            navController.navigate(Routes.WELCOME) {
                                popUpTo(Routes.SPLASH) { inclusive = true }
                            }
                        },
                        onNavigateToHome = {
                            navController.navigate(Routes.RESORT_LIST) {
                                popUpTo(Routes.SPLASH) { inclusive = true }
                            }
                        },
                    )
                }

                composable(Routes.WELCOME) {
                    WelcomeScreen(
                        onNavigateToOnboarding = {
                            navController.navigate(Routes.ONBOARDING)
                        },
                        onNavigateToHome = {
                            navController.navigate(Routes.RESORT_LIST) {
                                popUpTo(Routes.WELCOME) { inclusive = true }
                            }
                        },
                    )
                }

                composable(Routes.ONBOARDING) {
                    OnboardingScreen(
                        onComplete = {
                            navController.navigate(Routes.RESORT_LIST) {
                                popUpTo(Routes.ONBOARDING) { inclusive = true }
                            }
                        },
                    )
                }

                composable(Routes.RESORT_LIST) {
                    ResortListScreen(
                        onResortClick = { resortId ->
                            navController.navigate(Routes.resortDetail(resortId))
                        },
                    )
                }

                composable(
                    route = Routes.RESORT_DETAIL,
                    arguments = listOf(navArgument("resortId") { type = NavType.StringType }),
                ) { backStackEntry ->
                    val resortId = backStackEntry.arguments?.getString("resortId") ?: ""
                    ResortDetailScreen(
                        resortId = resortId,
                        onBackClick = { navController.popBackStack() },
                        onChatClick = { navController.navigate(Routes.CHAT) },
                        onConditionReportClick = {
                            navController.navigate(Routes.conditionReport(resortId))
                        },
                    )
                }

                composable(Routes.RESORT_MAP) {
                    ResortMapScreen(
                        onResortClick = { resortId ->
                            navController.navigate(Routes.resortDetail(resortId))
                        },
                    )
                }

                composable(Routes.BEST_SNOW) {
                    BestSnowScreen(
                        onResortClick = { resortId ->
                            navController.navigate(Routes.resortDetail(resortId))
                        },
                    )
                }

                composable(Routes.FAVORITES) {
                    FavoritesScreen(
                        onResortClick = { resortId ->
                            navController.navigate(Routes.resortDetail(resortId))
                        },
                        onCompareClick = {
                            navController.navigate(Routes.COMPARISON)
                        },
                    )
                }

                composable(Routes.SETTINGS) {
                    SettingsScreen(
                        onNotificationSettingsClick = {
                            navController.navigate(Routes.NOTIFICATION_SETTINGS)
                        },
                        onSignOut = {
                            navController.navigate(Routes.WELCOME) {
                                popUpTo(0) { inclusive = true }
                            }
                        },
                    )
                }

                composable(Routes.CHAT) {
                    ChatScreen(
                        onBackClick = { navController.popBackStack() },
                    )
                }

                composable(Routes.TRIPS) {
                    TripListScreen(
                        onBackClick = { navController.popBackStack() },
                        onResortClick = { resortId ->
                            navController.navigate(Routes.resortDetail(resortId))
                        },
                    )
                }

                composable(Routes.COMPARISON) {
                    ComparisonScreen(
                        onBackClick = { navController.popBackStack() },
                    )
                }

                composable(
                    route = Routes.CONDITION_REPORT,
                    arguments = listOf(navArgument("resortId") { type = NavType.StringType }),
                ) { backStackEntry ->
                    val resortId = backStackEntry.arguments?.getString("resortId") ?: ""
                    ConditionReportScreen(
                        resortId = resortId,
                        onBackClick = { navController.popBackStack() },
                    )
                }

                composable(Routes.NOTIFICATION_SETTINGS) {
                    NotificationSettingsScreen(
                        onBackClick = { navController.popBackStack() },
                    )
                }
            }
        }
    }
}
