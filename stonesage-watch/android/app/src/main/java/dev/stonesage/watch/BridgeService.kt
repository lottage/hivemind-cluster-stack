package dev.stonesage.watch

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.core.content.ContextCompat
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/** Holds the WebSocket to the bridge and relays frames to/from the watch. */
class BridgeService : Service() {

    companion object {
        private const val CHANNEL = "bridge"
        private const val NOTIF_ID = 1
        const val ACTION_STATUS = "dev.stonesage.watch.STATUS"
        @Volatile var lastStatus = "Stopped"

        fun start(ctx: Context) =
            ContextCompat.startForegroundService(ctx, Intent(ctx, BridgeService::class.java))

        fun stop(ctx: Context) = ctx.stopService(Intent(ctx, BridgeService::class.java))
    }

    private lateinit var prefs: Prefs
    private lateinit var relay: GarminRelay
    private val main = Handler(Looper.getMainLooper())
    private val http = OkHttpClient.Builder()
        .pingInterval(30, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()

    private var ws: WebSocket? = null
    private var backoffMs = 2_000L
    private var stopping = false
    private val outbox = ArrayDeque<String>()   // watch -> bridge frames while offline

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        prefs = Prefs(this)
        relay = GarminRelay(this, prefs.simulator, ::fromWatch, ::status)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        goForeground("Starting…")
        if (!prefs.configured) {
            status("Not configured"); stopSelf(); return START_NOT_STICKY
        }
        if (ws == null) {
            relay.start()
            connect()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        stopping = true
        main.removeCallbacksAndMessages(null)
        ws?.close(1000, "service stopped")
        relay.stop()
        status("Stopped")
        super.onDestroy()
    }

    // --- bridge side ---------------------------------------------------------

    private fun connect() {
        if (stopping) return
        val url = prefs.url.replaceFirst("https://", "wss://").replaceFirst("http://", "ws://") + "/ws/watch"
        val req = Request.Builder().url(url).header("Authorization", "Bearer ${prefs.token}").build()
        status("Connecting…")
        ws = http.newWebSocket(req, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                backoffMs = 2_000L
                status("Connected")
                synchronized(outbox) { while (outbox.isNotEmpty()) webSocket.send(outbox.removeFirst()) }
            }

            override fun onMessage(webSocket: WebSocket, text: String) = route(text)

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) = retry("closed $code")

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) =
                retry(if (response?.code == 403 || response?.code == 401) "bad token" else t.message ?: "error")
        })
    }

    private fun retry(why: String) {
        ws = null
        if (stopping) return
        status("Offline ($why), retry in ${backoffMs / 1000}s")
        main.postDelayed({ connect() }, backoffMs)
        backoffMs = (backoffMs * 2).coerceAtMost(60_000L)
    }

    private fun route(text: String) {
        val obj = try { JSONObject(text) } catch (_: Exception) { return }
        val msg = obj.toNative()
        when (obj.optString("k")) {
            "ask", "done", "err", "clr" -> relay.toApp(msg)
            "st", "use", "cfg" -> relay.toFace(msg)
        }
    }

    // --- watch side ----------------------------------------------------------

    private fun fromWatch(msg: Map<String, Any?>) {
        val frame = nativeToJson(msg).toString()
        val sock = ws
        if (sock == null || !sock.send(frame)) {
            synchronized(outbox) {
                outbox.addLast(frame)
                while (outbox.size > 20) outbox.removeFirst()
            }
        }
    }

    // --- notification / status ----------------------------------------------

    private fun status(s: String) {
        lastStatus = s
        sendBroadcast(Intent(ACTION_STATUS).setPackage(packageName))
        if (!stopping) getSystemService(NotificationManager::class.java).notify(NOTIF_ID, notification(s))
    }

    private fun notification(text: String): Notification {
        val nm = getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel(CHANNEL) == null) {
            nm.createNotificationChannel(
                NotificationChannel(CHANNEL, "Watch bridge", NotificationManager.IMPORTANCE_MIN)
            )
        }
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE
        )
        return Notification.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
            .setContentTitle("StoneSage bridge")
            .setContentText(text)
            .setContentIntent(open)
            .setOngoing(true)
            .build()
    }

    private fun goForeground(text: String) {
        startForeground(NOTIF_ID, notification(text), ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
    }
}
