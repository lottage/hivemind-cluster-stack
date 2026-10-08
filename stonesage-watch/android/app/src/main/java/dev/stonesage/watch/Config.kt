package dev.stonesage.watch

import android.content.Context

/** Must match the application ids in watch-app/manifest.xml and watch-face/manifest.xml. */
object Ids {
    const val WATCH_APP = "5ee31194fb424169944e5ae192a4e7d1"
    const val WATCH_FACE = "97b5e88982074e1dbb267e2c7141bd45"
}

class Prefs(ctx: Context) {
    private val sp = ctx.getSharedPreferences("bridge", Context.MODE_PRIVATE)

    /** e.g. https://bigserv.your-tailnet.ts.net:8443 */
    var url: String
        get() = sp.getString("url", "") ?: ""
        set(v) = sp.edit().putString("url", v.trim().trimEnd('/')).apply()

    var token: String
        get() = sp.getString("token", "") ?: ""
        set(v) = sp.edit().putString("token", v.trim()).apply()

    /** TETHERED mode talks to the Connect IQ simulator over `adb forward tcp:7381 tcp:7381`. */
    var simulator: Boolean
        get() = sp.getBoolean("sim", false)
        set(v) = sp.edit().putBoolean("sim", v).apply()

    val configured get() = url.isNotBlank() && token.isNotBlank()
}
