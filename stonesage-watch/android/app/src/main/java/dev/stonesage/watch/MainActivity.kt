package dev.stonesage.watch

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.text.InputType
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/** Minimal setup screen: bridge URL, phone token, start/stop, battery exemption. */
class MainActivity : Activity() {

    private lateinit var prefs: Prefs
    private lateinit var statusView: TextView

    private val statusReceiver = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) = refresh()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = Prefs(this)

        val url = EditText(this).apply {
            hint = "https://bigserv.your-tailnet.ts.net:8443"
            inputType = InputType.TYPE_TEXT_VARIATION_URI
            setText(prefs.url)
        }
        val token = EditText(this).apply {
            hint = "Phone token"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            setText(prefs.token)
        }
        val sim = CheckBox(this).apply {
            text = "Simulator mode (adb forward tcp:7381 tcp:7381)"
            isChecked = prefs.simulator
        }
        statusView = TextView(this).apply { textSize = 16f; setPadding(0, 24, 0, 24) }

        fun button(label: String, onClick: () -> Unit) =
            Button(this).apply { text = label; setOnClickListener { onClick() } }

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 48, 48, 48)
            addView(TextView(this@MainActivity).apply { text = "Bridge URL" })
            addView(url, MATCH_PARENT, WRAP_CONTENT)
            addView(TextView(this@MainActivity).apply { text = "Phone token" })
            addView(token, MATCH_PARENT, WRAP_CONTENT)
            addView(sim)
            addView(button("Save & start") {
                prefs.url = url.text.toString()
                prefs.token = token.text.toString()
                prefs.simulator = sim.isChecked
                BridgeService.stop(this@MainActivity)
                BridgeService.start(this@MainActivity)
            })
            addView(button("Stop") { BridgeService.stop(this@MainActivity) })
            addView(button("Allow unrestricted battery") { requestBatteryExemption() })
            addView(statusView)
            addView(TextView(this@MainActivity).apply {
                text = "Samsung: also add this app, Garmin Connect and Tailscale to " +
                    "Settings → Battery → Background usage limits → Never sleeping apps."
            })
        }
        setContentView(ScrollView(this).apply { addView(root) })

        if (Build.VERSION.SDK_INT >= 33) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
    }

    @SuppressLint("UnspecifiedRegisterReceiverFlag")
    override fun onResume() {
        super.onResume()
        val filter = IntentFilter(BridgeService.ACTION_STATUS)
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(statusReceiver, filter, RECEIVER_NOT_EXPORTED)
        else registerReceiver(statusReceiver, filter)
        refresh()
    }

    override fun onPause() {
        unregisterReceiver(statusReceiver)
        super.onPause()
    }

    private fun refresh() {
        val pm = getSystemService(PowerManager::class.java)
        val battery = if (pm.isIgnoringBatteryOptimizations(packageName)) "unrestricted" else "RESTRICTED"
        statusView.text = "Status: ${BridgeService.lastStatus}\nBattery: $battery"
    }

    @SuppressLint("BatteryLife")
    private fun requestBatteryExemption() {
        startActivity(
            Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                .setData(Uri.parse("package:$packageName"))
        )
    }
}
