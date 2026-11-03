package com.powderchaserapp.android.ui.screens.resortdetail

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.compose.SubcomposeAsyncImage
import com.powderchaserapp.android.R
import com.powderchaserapp.android.util.ResortEditSuggestion

/** Open a web page in a Custom Tab, falling back to any browser. */
fun openInBrowserTab(context: Context, url: String) {
    val uri = Uri.parse(url)
    try {
        CustomTabsIntent.Builder().setShowTitle(true).build().launchUrl(context, uri)
    } catch (_: ActivityNotFoundException) {
        try {
            context.startActivity(Intent(Intent.ACTION_VIEW, uri))
        } catch (_: ActivityNotFoundException) {
            // No browser installed; nothing sensible to do
        }
    }
}

/** Full-screen trail map image with pinch-to-zoom, pan and double-tap zoom (#187). */
@Composable
fun TrailMapViewerDialog(
    url: String,
    resortName: String,
    onOpenInBrowser: () -> Unit,
    onDismiss: () -> Unit,
) {
    var scale by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black),
        ) {
            SubcomposeAsyncImage(
                model = url,
                contentDescription = stringResource(R.string.trail_map_of, resortName),
                contentScale = ContentScale.Fit,
                loading = {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = Color.White)
                    }
                },
                error = {
                    Column(
                        Modifier.fillMaxSize(),
                        verticalArrangement = Arrangement.Center,
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(stringResource(R.string.trail_map_load_failed), color = Color.White)
                        Spacer(Modifier.height(12.dp))
                        OutlinedButton(onClick = onOpenInBrowser) {
                            Text(stringResource(R.string.open_in_browser))
                        }
                    }
                },
                modifier = Modifier
                    .fillMaxSize()
                    .pointerInput(Unit) {
                        detectTransformGestures { _, pan, zoom, _ ->
                            scale = (scale * zoom).coerceIn(1f, 6f)
                            offset = if (scale == 1f) Offset.Zero else offset + pan
                        }
                    }
                    .pointerInput(Unit) {
                        detectTapGestures(
                            onDoubleTap = {
                                if (scale > 1f) {
                                    scale = 1f
                                    offset = Offset.Zero
                                } else {
                                    scale = 2.5f
                                }
                            },
                        )
                    }
                    .graphicsLayer(
                        scaleX = scale,
                        scaleY = scale,
                        translationX = offset.x,
                        translationY = offset.y,
                    ),
            )

            Row(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(8.dp),
            ) {
                IconButton(onClick = onOpenInBrowser) {
                    Icon(
                        Icons.AutoMirrored.Filled.OpenInNew,
                        contentDescription = stringResource(R.string.open_in_browser),
                        tint = Color.White,
                    )
                }
                IconButton(onClick = onDismiss) {
                    Icon(Icons.Default.Close, contentDescription = stringResource(R.string.close), tint = Color.White)
                }
            }
        }
    }
}

/** "Suggest an Edit" form, same sections and payload as iOS and web (#189). */
@Composable
fun SuggestEditDialog(
    resortName: String,
    status: SuggestEditStatus,
    onSubmit: (section: String, suggestion: String) -> Unit,
    onDismiss: () -> Unit,
) {
    var section by remember { mutableStateOf("") }
    var suggestion by remember { mutableStateOf("") }
    val submitting = status == SuggestEditStatus.Submitting

    if (status == SuggestEditStatus.Sent) {
        AlertDialog(
            onDismissRequest = onDismiss,
            title = { Text(stringResource(R.string.suggest_edit_thanks_title)) },
            text = { Text(stringResource(R.string.suggest_edit_thanks_body)) },
            confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.done)) } },
        )
        return
    }

    AlertDialog(
        onDismissRequest = { if (!submitting) onDismiss() },
        title = { Text(stringResource(R.string.suggest_edit)) },
        text = {
            Column {
                Text(
                    resortName,
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                Text(stringResource(R.string.suggest_edit_section), style = MaterialTheme.typography.labelLarge)
                ResortEditSuggestion.sections.forEach { option ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .selectable(
                                selected = section == option,
                                onClick = { section = option },
                                role = Role.RadioButton,
                                enabled = !submitting,
                            )
                            .padding(vertical = 2.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(selected = section == option, onClick = null, enabled = !submitting)
                        Spacer(Modifier.width(8.dp))
                        Text(option, style = MaterialTheme.typography.bodyMedium)
                    }
                }
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = suggestion,
                    onValueChange = { suggestion = it.take(ResortEditSuggestion.MAX_SUGGESTION_LENGTH) },
                    label = { Text(stringResource(R.string.suggest_edit_correction)) },
                    supportingText = {
                        Text(stringResource(R.string.suggest_edit_min_length, ResortEditSuggestion.MIN_SUGGESTION_LENGTH))
                    },
                    minLines = 3,
                    maxLines = 6,
                    enabled = !submitting,
                    modifier = Modifier.fillMaxWidth(),
                )
                if (status is SuggestEditStatus.Failed) {
                    Text(
                        status.message,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onSubmit(section, suggestion) },
                enabled = !submitting && ResortEditSuggestion.isValid(section, suggestion),
            ) {
                if (submitting) {
                    CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                } else {
                    Text(stringResource(R.string.submit))
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !submitting) { Text(stringResource(R.string.cancel)) }
        },
    )
}
