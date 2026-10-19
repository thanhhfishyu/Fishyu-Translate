package com.fishyu.translate

import android.annotation.SuppressLint
import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.graphics.Rect
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.IBinder
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ImageView
import android.widget.Toast
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlin.math.abs
import kotlin.math.hypot

class BubbleService : Service() {

    companion object {
        const val ACTION_START = "start"
        const val ACTION_STOP = "stop"
        const val EXTRA_CODE = "code"
        const val EXTRA_DATA = "data"
        const val EXTRA_TOKEN = "token"
        private var usedToken = 0L
        @Volatile var running = false
            private set

        fun stop(ctx: Context) {
            ctx.startService(Intent(ctx, BubbleService::class.java).setAction(ACTION_STOP))
        }
    }

    private val errors = CoroutineExceptionHandler { _, e ->
        CrashLog.save(this, e, "BubbleService")
        toast("Lỗi: ${CrashLog.shortReason(e)}")
    }
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main + errors)
    private lateinit var wm: WindowManager
    private var projection: MediaProjection? = null
    private var capturer: ScreenCapturer? = null

    private var bubble: View? = null
    private var bubbleLp: WindowManager.LayoutParams? = null
    private var menu: View? = null
    private var selector: RegionSelectView? = null
    private var panel: View? = null
    private var card: ResultCard? = null
    private var capturing = false
    private var live: LiveSession? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        wm = getSystemService(WindowManager::class.java)
        Dictionary.preload(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> { stopSelf(); return START_NOT_STICKY }
            ACTION_START -> {
                val token = intent.getLongExtra(EXTRA_TOKEN, 0L)
                if (token != 0L && token == usedToken) return START_NOT_STICKY
                usedToken = token
                try {
                    startForegroundCompat()
                } catch (e: Throwable) {
                    CrashLog.save(this, e, "startForeground")
                    toast("Không bật được bong bóng: ${CrashLog.shortReason(e)}")
                    stopSelf()
                    return START_NOT_STICKY
                }
                val code = intent.getIntExtra(EXTRA_CODE, 0)
                @Suppress("DEPRECATION")
                val data: Intent? = if (Build.VERSION.SDK_INT >= 33)
                    intent.getParcelableExtra(EXTRA_DATA, Intent::class.java)
                else intent.getParcelableExtra(EXTRA_DATA)
                if (data == null) { stopSelf(); return START_NOT_STICKY }
                try {
                    setupProjection(code, data)
                } catch (e: Throwable) {
                    CrashLog.save(this, e, "setupProjection")
                    capturer = null
                    runCatching { projection?.stop() }
                    projection = null
                    toast("Không lấy được quyền chụp màn hình: ${CrashLog.shortReason(e)}. Bong bóng vẫn dùng được cho \"Dịch chữ đã copy\".")
                }
                try {
                    if (bubble == null) showBubble()
                } catch (e: Throwable) {
                    CrashLog.save(this, e, "showBubble")
                    toast("Không hiện được bong bóng: ${CrashLog.shortReason(e)}")
                    stopSelf()
                    return START_NOT_STICKY
                }
                running = true
            }
        }
        return START_NOT_STICKY
    }

    private fun startForegroundCompat() {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, 1,
            Intent(this, BubbleService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE)
        val n: Notification = NotificationCompat.Builder(this, App.CHANNEL)
            .setSmallIcon(R.drawable.ic_tile)
            .setContentTitle("Bong bóng dịch đang bật")
            .setContentText("Chạm bong bóng để dịch, giữ để mở menu")
            .setContentIntent(open)
            .addAction(0, "Tắt", stop)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else startForeground(1, n)
    }

    private fun setupProjection(code: Int, data: Intent) {
        stopLive()
        runCatching { capturer?.release() }
        capturer = null
        runCatching { projection?.stop() }
        projection = null
        val mpm = getSystemService(MediaProjectionManager::class.java)
        val mp = mpm.getMediaProjection(code, data) ?: run { stopSelf(); return }
        projection = mp
        capturer = ScreenCapturer(this, mp) {
            scope.launch { stopSelf() }
        }
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        val c = capturer
        val before = c?.let { it.width to it.height }
        c?.onConfigChanged()
        removeSelector()
        if (live != null && c != null && before != (c.width to c.height)) {
            stopLive()
            toast("Màn hình đã xoay, hãy chọn lại vùng dịch trực tiếp")
        }
    }

    override fun onDestroy() {
        running = false
        removeView(bubble); bubble = null
        stopLive()
        runCatching { removeMenu(); removeSelector(); removePanel() }
        runCatching { capturer?.release() }; capturer = null
        runCatching { projection?.stop() }; projection = null
        scope.cancel()
        super.onDestroy()
    }

    private fun overlayType() = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY

    @SuppressLint("ClickableViewAccessibility")
    private fun showBubble() {
        val p = Palette(this)
        val size = dp(56)
        val v = ImageView(this).apply {
            setImageResource(R.drawable.bubble_shark)
            alpha = 0.95f
        }
        val lp = WindowManager.LayoutParams(
            size, size, overlayType(),
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            val sw = resources.displayMetrics.widthPixels
            x = if (Prefs.bubbleX < 0) sw - size - dp(4) else Prefs.bubbleX
            y = Prefs.bubbleY
        }

        var downX = 0f; var downY = 0f; var startX = 0; var startY = 0
        var moved = false; var longPressed = false
        val longPress = Runnable { if (!moved) { longPressed = true; showMenu() } }
        v.setOnTouchListener { _, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    downX = e.rawX; downY = e.rawY; startX = lp.x; startY = lp.y
                    moved = false; longPressed = false
                    v.postDelayed(longPress, 450)
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = e.rawX - downX; val dy = e.rawY - downY
                    if (!moved && hypot(dx, dy) > dp(8)) { moved = true; v.removeCallbacks(longPress) }
                    if (moved) {
                        lp.x = startX + dx.toInt(); lp.y = startY + dy.toInt()
                        wm.updateViewLayout(v, lp)
                    }
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    v.removeCallbacks(longPress)
                    if (moved) snapToEdge(v, lp)
                    else if (!longPressed && e.actionMasked == MotionEvent.ACTION_UP) onBubbleTap()
                }
            }
            true
        }
        wm.addView(v, lp)
        bubble = v; bubbleLp = lp
    }

    private fun snapToEdge(v: View, lp: WindowManager.LayoutParams) {
        val sw = resources.displayMetrics.widthPixels
        val sh = resources.displayMetrics.heightPixels
        lp.x = if (lp.x + v.width / 2 < sw / 2) dp(4) - 0 else sw - v.width - dp(4)
        lp.y = lp.y.coerceIn(dp(24), sh - v.height - dp(24))
        wm.updateViewLayout(v, lp)
        Prefs.bubbleX = lp.x; Prefs.bubbleY = lp.y
    }

    private fun onBubbleTap() {
        if (menu != null) { removeMenu(); return }
        startCapture()
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun showMenu() {
        removeMenu()
        val p = Palette(this)
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = doodle(p, p.bg, dpf(16f), dp(3))
            setPadding(dp(6), dp(6), dp(9), dp(9))
        }
        fun item(t: String, act: () -> Unit) {
            box.addView(label(t, 15f, p.fg).apply {
                typeface = Fonts.medium(this@BubbleService)
                setPadding(dp(14), dp(9), dp(18), dp(9))
                isClickable = true
                setOnClickListener { removeMenu(); act() }
            })
        }
        item("Khoanh vùng để dịch") { startCapture() }
        if (live == null) item("Dịch trực tiếp (game)") { startCapture(liveMode = true) }
        else item("Dừng dịch trực tiếp") { stopLive() }
        item("Dịch chữ đã copy") { openTranslate(fromClipboard = true) }
        item("Ngôn ngữ: ${Prefs.sourceLang.label}") {
            Prefs.sourceLang = Prefs.sourceLang.next()
            toast("Ngôn ngữ nguồn: ${Prefs.sourceLang.label}")
        }
        item("Cài đặt") {
            startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
        item("Tắt bong bóng") { stopSelf() }

        val blp = bubbleLp ?: return
        val sw = resources.displayMetrics.widthPixels
        val lp = WindowManager.LayoutParams(
            -2, -2, overlayType(),
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or (if (blp.x > sw / 2) Gravity.END else Gravity.START)
            x = dp(64)
            y = (blp.y - dp(40)).coerceAtLeast(dp(24))
        }
        box.setOnTouchListener { _, e ->
            if (e.actionMasked == MotionEvent.ACTION_OUTSIDE) { removeMenu(); true } else false
        }
        wm.addView(box, lp)
        menu = box
    }

    private fun removeMenu() { removeView(menu); menu = null }

    private fun startCapture(liveMode: Boolean = false) {
        val cap = capturer ?: run {
            toast("Chưa có quyền chụp màn hình. Hãy tắt rồi bật lại bong bóng, hoặc giữ bong bóng để dịch chữ đã copy")
            return
        }
        if (capturing) return
        capturing = true
        removePanel()
        live?.setHidden(true)
        bubble?.visibility = View.INVISIBLE
        scope.launch {
            val shot = try { cap.capture() } catch (e: Exception) { null }
            capturing = false
            if (shot == null) {
                bubble?.visibility = View.VISIBLE
                live?.setHidden(false)
                toast("Chưa chụp được màn hình. Nếu vẫn lỗi, hãy tắt rồi bật lại bong bóng và chọn \"Toàn bộ màn hình\"")
                return@launch
            }
            if (liveMode) showLiveSelector(shot) else showSelector(shot)
        }
    }

    private fun savedLiveRegion(): Rect? {
        val c = capturer ?: return null
        val v = Prefs.liveRegion.split(',').mapNotNull { it.toIntOrNull() }
        if (v.size != 6 || v[4] != c.width || v[5] != c.height) return null
        return Rect(v[0], v[1], v[2], v[3])
    }

    private fun showLiveSelector(shot: Bitmap) {
        val saved = savedLiveRegion()
        lateinit var view: RegionSelectView
        view = RegionSelectView(this, shot,
            onRegion = { r -> removeSelector(); startLive(r) },
            onTap = { x, y -> view.setBusy("Đang tìm khung chữ..."); liveBlockAt(shot, x, y) },
            onWholeScreen = {
                removeSelector()
                startLive(saved ?: Rect(0, 0, shot.width, shot.height))
            },
            onCancel = { removeSelector() },
            hint = "Khoanh vùng khung thoại để dịch liên tục",
            secondLabel = if (saved != null) "Vùng lần trước" else "Cả màn hình",
        )
        addSelector(view)
    }

    private fun liveBlockAt(shot: Bitmap, x: Int, y: Int) {
        scope.launch {
            val blocks = try { OcrEngine.raw(shot).first.textBlocks.mapNotNull { it.boundingBox } } catch (e: Exception) { emptyList() }
            val hit = blocks.firstOrNull { Rect(it).apply { inset(-dp(14), -dp(14)) }.contains(x, y) }
            removeSelector()
            if (hit == null) { toast("Không thấy chữ ở chỗ này, hãy kéo để khoanh vùng"); return@launch }
            val r = Rect(hit).apply { inset(-dp(24), -dp(16)) }
            r.intersect(0, 0, shot.width, shot.height)
            startLive(r)
        }
    }

    private fun startLive(r: Rect) {
        val cap = capturer ?: return
        stopLive()
        removePanel()
        Prefs.liveRegion = "${r.left},${r.top},${r.right},${r.bottom},${cap.width},${cap.height}"
        val s = LiveSession(this, wm, scope, cap, r,
            obstacles = { listOfNotNull(bubbleRect()) },
            onClose = { stopLive() })
        live = s
        s.start()
        bubble?.visibility = View.VISIBLE
    }

    private fun stopLive() {
        live?.stop()
        live = null
    }

    private fun bubbleRect(): Rect? {
        val b = bubble ?: return null
        if (b.visibility != View.VISIBLE || !b.isAttachedToWindow) return null
        val loc = IntArray(2)
        b.getLocationOnScreen(loc)
        return Rect(loc[0], loc[1], loc[0] + b.width, loc[1] + b.height)
    }

    private fun showSelector(shot: Bitmap) {
        lateinit var view: RegionSelectView
        view = RegionSelectView(this, shot,
            onRegion = { r ->
                val crop = Bitmap.createBitmap(shot, r.left, r.top, r.width(), r.height())
                removeSelector()
                translateImage(crop, anchor = r)
            },
            onTap = { x, y -> view.setBusy("Đang tìm đoạn chữ..."); translateBlockAt(shot, x, y) },
            onWholeScreen = { view.setBusy("Đang nhận diện cả màn hình..."); translateWhole(shot) },
            onCancel = { removeSelector() }
        )
        addSelector(view)
    }

    private fun addSelector(view: RegionSelectView) {
        removeSelector()
        bubble?.visibility = View.INVISIBLE
        val lp = WindowManager.LayoutParams(
            -1, -1, overlayType(),
            WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            if (Build.VERSION.SDK_INT >= 28) layoutInDisplayCutoutMode =
                if (Build.VERSION.SDK_INT >= 30) WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
                else WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
        }
        wm.addView(view, lp)
        selector = view
    }

    private fun removeSelector() {
        removeView(selector); selector = null
        live?.setHidden(false)
        if (panel == null) bubble?.visibility = View.VISIBLE
    }

    private fun translateImage(crop: Bitmap, anchor: Rect) {
        val c = showPanel(anchor)
        c.showLoading("Đang nhận diện chữ...")
        scope.launch {
            try {
                val r = OcrEngine.recognize(crop)
                c.start(r.text, r.lang)
            } catch (e: Exception) {
                c.showError("Lỗi nhận diện chữ: ${e.message}")
            }
        }
    }

    private fun translateBlockAt(shot: Bitmap, x: Int, y: Int) {
        scope.launch {
            try {
                val (text, lang) = OcrEngine.raw(shot)
                val blocks = text.textBlocks.filter { it.boundingBox != null }
                val pad = dp(14)
                val hit = blocks.firstOrNull { b -> Rect(b.boundingBox).apply { inset(-pad, -pad) }.contains(x, y) }
                    ?: blocks.minByOrNull { b ->
                        val r = b.boundingBox!!
                        abs(r.centerY() - y) + abs(r.centerX() - x) / 2
                    }?.takeIf { b ->
                        val r = b.boundingBox!!
                        abs(r.centerY() - y) < dp(80) + r.height() / 2
                    }
                if (hit == null) {
                    selector?.setBusy("Không thấy chữ ở chỗ này")
                    kotlinx.coroutines.delay(900)
                    removeSelector()
                    return@launch
                }
                val idx = blocks.indexOf(hit)
                val ctxText = blocks.subList(maxOf(0, idx - 1), minOf(blocks.size, idx + 2))
                    .joinToString("\n") { OcrEngine.assembleBlock(it) }
                removeSelector()
                val c = showPanel(hit.boundingBox!!)
                c.start(OcrEngine.assembleBlock(hit), lang, ctxText)
            } catch (e: Exception) {
                removeSelector()
                toast("Lỗi: ${e.message}")
            }
        }
    }

    private fun translateWhole(shot: Bitmap) {
        scope.launch {
            try {
                val r = OcrEngine.recognize(shot)
                removeSelector()
                val c = showPanel(null)
                c.start(r.text, r.lang)
            } catch (e: Exception) {
                removeSelector(); toast("Lỗi: ${e.message}")
            }
        }
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun showPanel(anchor: Rect?): ResultCard {
        removePanel()
        val sw = resources.displayMetrics.widthPixels
        val sh = resources.displayMetrics.heightPixels
        val c = ResultCard(this, scope, (sh * 0.42).toInt()) { removePanel() }
        val frame = object : FrameLayout(this) {
            override fun dispatchKeyEvent(event: KeyEvent): Boolean {
                if (event.keyCode == KeyEvent.KEYCODE_BACK && event.action == KeyEvent.ACTION_UP) {
                    removePanel(); return true
                }
                return super.dispatchKeyEvent(event)
            }
        }.apply { addView(c) }
        val width = minOf(sw - dp(16), dp(560))
        val atTop = anchor != null && anchor.centerY() > sh / 2
        val lp = WindowManager.LayoutParams(
            width, -2, overlayType(),
            WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = (if (atTop) Gravity.TOP else Gravity.BOTTOM) or Gravity.CENTER_HORIZONTAL
            y = if (atTop) dp(40) else dp(28)
            softInputMode = WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE
        }
        var downY = 0f; var startY = 0
        c.header.setOnTouchListener { _, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> { downY = e.rawY; startY = lp.y }
                MotionEvent.ACTION_MOVE -> {
                    val dy = (e.rawY - downY).toInt()
                    lp.y = (startY + if (lp.gravity and Gravity.TOP == Gravity.TOP) dy else -dy).coerceAtLeast(0)
                    wm.updateViewLayout(frame, lp)
                }
            }
            true
        }
        wm.addView(frame, lp)
        panel = frame; card = c
        bubble?.visibility = View.VISIBLE
        return c
    }

    private fun removePanel() { removeView(panel); panel = null; card = null }

    private fun openTranslate(fromClipboard: Boolean) {
        startActivity(Intent(this, TranslateActivity::class.java)
            .putExtra(TranslateActivity.EXTRA_CLIPBOARD, fromClipboard)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    private fun removeView(v: View?) {
        if (v != null) runCatching { wm.removeView(v) }
    }

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()
}
