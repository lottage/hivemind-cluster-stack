package dev.stonesage.watch

import android.content.Context
import com.garmin.android.connectiq.ConnectIQ
import com.garmin.android.connectiq.IQApp
import com.garmin.android.connectiq.IQDevice

/**
 * Thin wrapper over the Connect IQ companion SDK.
 * If a listener signature doesn't match your SDK version, let Android Studio
 * "Implement members" regenerate it; the bodies stay the same.
 */
class GarminRelay(
    private val ctx: Context,
    simulator: Boolean,
    private val onWatchMessage: (Map<String, Any?>) -> Unit,
    private val log: (String) -> Unit,
) {
    private val ciq: ConnectIQ = ConnectIQ.getInstance(
        ctx,
        if (simulator) ConnectIQ.IQConnectType.TETHERED else ConnectIQ.IQConnectType.WIRELESS,
    )
    private val app = IQApp(Ids.WATCH_APP)
    private val face = IQApp(Ids.WATCH_FACE)

    @Volatile private var ready = false
    @Volatile private var device: IQDevice? = null

    fun start() {
        ciq.initialize(ctx, true, object : ConnectIQ.ConnectIQListener {
            override fun onSdkReady() {
                ready = true
                attach()
            }
            override fun onInitializeError(status: ConnectIQ.IQSdkErrorStatus) {
                log("Connect IQ init failed: $status")
            }
            override fun onSdkShutDown() {
                ready = false
            }
        })
    }

    private fun attach() {
        val d = try {
            ciq.knownDevices?.firstOrNull()
        } catch (e: Exception) {
            log("device lookup failed: ${e.message}"); null
        } ?: run { log("No paired Garmin device in Garmin Connect"); return }
        device = d
        log("Watch: ${d.friendlyName}")

        ciq.registerForDeviceEvents(d, object : ConnectIQ.IQDeviceEventListener {
            override fun onDeviceStatusChanged(device: IQDevice, status: IQDevice.IQDeviceStatus) {
                log("Watch ${status.name.lowercase()}")
            }
        })
        ciq.registerForAppEvents(d, app, object : ConnectIQ.IQApplicationEventListener {
            override fun onMessageReceived(
                device: IQDevice, app: IQApp, message: List<Any>, status: ConnectIQ.IQMessageStatus,
            ) {
                if (status != ConnectIQ.IQMessageStatus.SUCCESS) return
                message.forEach { m ->
                    (m as? Map<*, *>)?.let { map ->
                        onWatchMessage(map.entries.associate { it.key.toString() to it.value })
                    }
                }
            }
        })
    }

    fun toApp(msg: Map<String, Any>) = send(app, msg)
    fun toFace(msg: Map<String, Any>) = send(face, msg)

    private fun send(target: IQApp, msg: Map<String, Any>) {
        val d = device ?: return
        if (!ready) return
        try {
            ciq.sendMessage(d, target, msg, object : ConnectIQ.IQSendMessageListener {
                override fun onMessageStatus(device: IQDevice, app: IQApp, status: ConnectIQ.IQMessageStatus) {
                    if (status != ConnectIQ.IQMessageStatus.SUCCESS) log("send ${msg["k"]}: $status")
                }
            })
        } catch (e: Exception) {
            log("send failed: ${e.message}")
        }
    }

    fun stop() {
        try {
            ciq.unregisterAllForEvents()
            ciq.shutdown(ctx)
        } catch (_: Exception) {
        }
    }
}
