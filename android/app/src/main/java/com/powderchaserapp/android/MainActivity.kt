package com.powderchaserapp.android

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.powderchaserapp.android.service.NetworkMonitor
import com.powderchaserapp.android.ui.navigation.PowderChaserNavHost
import com.powderchaserapp.android.ui.theme.PowderChaserTheme
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var networkMonitor: NetworkMonitor

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            PowderChaserTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    PowderChaserNavHost(networkMonitor = networkMonitor)
                }
            }
        }
    }
}
