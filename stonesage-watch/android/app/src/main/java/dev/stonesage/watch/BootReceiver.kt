package dev.stonesage.watch

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        // Boot, or this app was just updated (the update killed the running service). Both broadcasts are allowed to
        // start a foreground service from the background.
        val restart = intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_MY_PACKAGE_REPLACED
        if (restart && Prefs(ctx).configured) {
            BridgeService.start(ctx)
        }
    }
}
