package com.fishyu.translate

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.Rect
import android.os.Build
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.TextView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.abs

class LiveSession(
    private val ctx: Context,
    private val wm: WindowManager,
    private val scope: CoroutineScope,
    private val capturer: ScreenCapturer,
    val region: Rect,
    private val obstacles: () -> List<Rect>,
    private val onClose: () -> Unit,
) {
    private val p = Palette(ctx)
    private var frame: View? = null
    private var box: LinearLayout? = null
    private lateinit var boxLp: WindowManager.LayoutParams
    private lateinit var status: TextView
    private lateinit var engineChip: TextView
    private lateinit var pauseChip: TextView
    private lateinit var translation: TextView
    private lateinit var source: TextView
    private var job: Job? = null
    private var paused = false
    private var lastOcrSig: IntArray? = null
    private var lastOcrAt = 0L
    private var pendingNorm = ""
    private var shownNorm = ""
    private var emptyStreak = 0
    private var sentChars = 0
    private val history = ArrayDeque<String>()
    private val done = LinkedHashMap<String, String>()

    fun start() {
        showFrame()
        showBox()
        loop()
    }

    fun stop() {
        job?.cancel()
        runCatching { frame?.let { wm.removeView(it) } }
        runCatching { box?.let { wm.removeView(it) } }
        frame = null; box = null
    }

    private var hidden = false

    fun setHidden(h: Boolean) {
        hidden = h
        val v = if (h) View.INVISIBLE else View.VISIBLE
        frame?.visibility = v
        box?.visibility = v
        if (!h) lastOcrAt = System.currentTimeMillis() + 400
    }

    fun boxRect(): Rect? {
        val b = box ?: return null
        if (!b.isAttachedToWindow) return null
        val loc = IntArray(2)
        b.getLocationOnScreen(loc)
        return Rect(loc[0], loc[1], loc[0] + b.width, loc[1] + b.height)
    }

    private fun baseLp(w: Int, h: Int, flags: Int) = WindowManager.LayoutParams(
        w, h, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
        flags or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
        PixelFormat.TRANSLUCENT
    ).apply {
        gravity = Gravity.TOP or Gravity.START
        if (Build.VERSION.SDK_INT >= 30) layoutInDisplayCutoutMode =
            WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
        else if (Build.VERSION.SDK_INT >= 28) layoutInDisplayCutoutMode =
            WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
    }

    private fun showFrame() {
        val pad = ctx.dp(4)
        val v = object : View(ctx) {
            val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = p.accent; style = Paint.Style.STROKE; strokeWidth = ctx.dpf(2f)
                pathEffect = DashPathEffect(floatArrayOf(ctx.dpf(7f), ctx.dpf(5f)), 0f)
            }
            override fun onDraw(c: Canvas) {
                val s = paint.strokeWidth
                c.drawRoundRect(s, s, width - s, height - s, ctx.dpf(6f), ctx.dpf(6f), paint)
            }
        }
        val lp = baseLp(region.width() + pad * 2, region.height() + pad * 2,
            WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE)
        lp.x = region.left - pad
        lp.y = region.top - pad
        wm.addView(v, lp)
        frame = v
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun showBox() {
        val sw = capturer.width
        val sh = capturer.height
        val b = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            background = ctx.doodle(p, p.bg, ctx.dpf(16f), ctx.dp(3))
            setPadding(ctx.dp(12), ctx.dp(8), ctx.dp(14), ctx.dp(12))
            alpha = 0.96f
        }
        status = ctx.label("Đang theo dõi - chạm vào bản dịch để hiện/ẩn chữ gốc", 11f, p.muted).apply { typeface = Fonts.medium(ctx) }
        engineChip = ctx.chip(engineLabel(), p) {
            Prefs.liveEngine = if (Prefs.liveEngine == Engine.DEEPL) Engine.OFFLINE else Engine.DEEPL
            engineChip.text = engineLabel()
            done.clear()
            shownNorm = ""
            lastOcrSig = null
        }
        val smaller = ctx.chip("A-", p) { Prefs.liveFontSp = Prefs.liveFontSp - 2; applyFont() }
        val bigger = ctx.chip("A+", p) { Prefs.liveFontSp = Prefs.liveFontSp + 2; applyFont() }
        pauseChip = ctx.chip("Dừng", p) { togglePause() }
        val close = ctx.chip("Đóng", p, filled = true) { onClose() }
        val header = ctx.hbox(engineChip, smaller, bigger, pauseChip, ctx.spacer(), close, gap = 6)
        b.addView(header, LinearLayout.LayoutParams(-1, -2))

        source = ctx.label("", 12f, p.muted).apply {
            visibility = if (Prefs.liveShowSource) View.VISIBLE else View.GONE
            setPadding(0, ctx.dp(6), 0, 0)
        }
        b.addView(source)
        translation = ctx.label("Đang đọc chữ trong vùng...", Prefs.liveFontSp.toFloat(), p.fg).apply {
            setLineSpacing(0f, 1.2f)
            setPadding(0, ctx.dp(6), 0, 0)
            setOnClickListener {
                Prefs.liveShowSource = !Prefs.liveShowSource
                source.visibility = if (Prefs.liveShowSource) View.VISIBLE else View.GONE
            }
        }
        b.addView(translation)
        status.setPadding(0, ctx.dp(4), 0, 0)
        b.addView(status)

        val width = region.width().coerceIn(ctx.dp(300), sw - ctx.dp(16))
        boxLp = baseLp(width, -2, WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
            WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL)
        boxLp.x = (region.centerX() - width / 2).coerceIn(ctx.dp(8), sw - width - ctx.dp(8))
        val guess = ctx.dp(110)
        boxLp.y = if (region.top > guess + ctx.dp(16)) region.top - guess - ctx.dp(10)
        else (region.bottom + ctx.dp(10)).coerceAtMost(sh - guess)

        var dx = 0f; var dy = 0f; var sx = 0; var sy = 0
        header.setOnTouchListener { _, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> { dx = e.rawX; dy = e.rawY; sx = boxLp.x; sy = boxLp.y }
                MotionEvent.ACTION_MOVE -> {
                    boxLp.x = sx + (e.rawX - dx).toInt()
                    boxLp.y = sy + (e.rawY - dy).toInt()
                    wm.updateViewLayout(b, boxLp)
                }
            }
            true
        }
        wm.addView(b, boxLp)
        box = b
        b.post { fitBox() }
    }

    private fun fitBox() {
        val b = box ?: return
        val sh = capturer.height
        if (boxLp.y < region.top && boxLp.y + b.height > region.top - ctx.dp(4)) {
            boxLp.y = (region.top - b.height - ctx.dp(10)).coerceAtLeast(0)
            wm.updateViewLayout(b, boxLp)
        } else if (boxLp.y + b.height > sh) {
            boxLp.y = (sh - b.height).coerceAtLeast(0)
            wm.updateViewLayout(b, boxLp)
        }
    }

    private fun engineLabel() = if (Prefs.liveEngine == Engine.DEEPL) "DeepL" else "Offline"

    private fun applyFont() {
        translation.setTextSize(TypedValue.COMPLEX_UNIT_SP, Prefs.liveFontSp.toFloat())
        translation.post { fitBox() }
    }

    private fun togglePause() {
        paused = !paused
        pauseChip.text = if (paused) "Tiếp" else "Dừng"
        status.text = if (paused) "Đã dừng" else "Đang theo dõi"
        if (!paused) { lastOcrSig = null; pendingNorm = ""; shownNorm = "" }
    }

    private fun loop() {
        job = scope.launch {
            status.text = "Đang đọc chữ..."
            while (isActive) {
                if (paused || hidden) { delay(400); continue }
                val obs = obstacles() + listOfNotNull(boxRect())
                val bmp = withContext(Dispatchers.Default) { capturer.grabRegion(region)?.also { mask(it, obs) } }
                if (bmp == null) { delay(400); continue }
                val sig = withContext(Dispatchers.Default) { signature(bmp) }
                val prev = lastOcrSig
                val changed = prev == null || diff(prev, sig) >= 3
                val now = System.currentTimeMillis()
                if ((changed || pendingNorm.isNotEmpty()) && now - lastOcrAt >= 650) {
                    lastOcrSig = sig
                    lastOcrAt = now
                    process(bmp)
                }
                delay(350)
            }
        }
    }

    private fun mask(bmp: Bitmap, obs: List<Rect>) {
        val c = Canvas(bmp)
        val fill = Paint().apply { color = bmp.getPixel(0, 0) }
        for (o in obs) {
            val r = Rect(o)
            if (!r.intersect(region)) continue
            r.offset(-region.left, -region.top)
            c.drawRect(r, fill)
        }
    }

    private suspend fun process(bmp: Bitmap) {
        val ocr = try { OcrEngine.recognize(bmp) } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e
            return
        }
        val text = ocr.text.replace("\n", "").trim()
        val norm = normalize(text)
        if (norm.length < 2) {
            pendingNorm = ""
            if (++emptyStreak == 3 && shownNorm.isEmpty()) status.text = "Chưa thấy chữ trong vùng đã chọn"
            return
        }
        emptyStreak = 0
        if (similarity(norm, shownNorm) >= 0.8) { pendingNorm = ""; return }
        if (similarity(norm, pendingNorm) < 0.9) {
            pendingNorm = norm
            return
        }
        pendingNorm = ""
        shownNorm = norm
        source.text = text

        val reuse = done.entries.firstOrNull { similarity(it.key, norm) >= 0.85 }?.value
        if (reuse != null) {
            translation.text = reuse
            translation.post { fitBox() }
            return
        }

        status.text = "Đang dịch..."
        translation.alpha = 0.55f
        try {
            val ctxText = history.joinToString("\n").ifBlank { null }
            val r = Translator.translate(text, ocr.lang, ctxText, Prefs.liveEngine)
            translation.text = r.text
            if (r.engine == "DeepL") sentChars += text.length
            done[norm] = r.text
            if (done.size > 40) done.remove(done.keys.first())
            status.text = when {
                r.note != null -> "Đang dịch offline (DeepL lỗi)"
                Prefs.liveEngine == Engine.DEEPL -> "Đang theo dõi - đã gửi DeepL khoảng $sentChars ký tự"
                else -> "Đang theo dõi"
            }
        } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e
            status.text = "Lỗi: ${e.message?.take(60)}"
            shownNorm = ""
        }
        translation.alpha = 1f
        history.addLast(text)
        while (history.size > 3) history.removeFirst()
        translation.post { fitBox() }
    }

    private fun normalize(s: String): String = buildString {
        for (c in s) if (Character.isLetterOrDigit(c)) append(c)
    }

    private fun similarity(a: String, b: String): Double {
        if (a == b) return 1.0
        if (a.isEmpty() || b.isEmpty()) return 0.0
        val n = a.length
        val m = b.length
        var prev = IntArray(m + 1) { it }
        var cur = IntArray(m + 1)
        for (i in 1..n) {
            cur[0] = i
            for (j in 1..m) {
                val cost = if (a[i - 1] == b[j - 1]) 0 else 1
                cur[j] = minOf(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            }
            val t = prev; prev = cur; cur = t
        }
        return 1.0 - prev[m].toDouble() / maxOf(n, m)
    }

    private fun signature(b: Bitmap): IntArray {
        val w = 48
        val h = (48f * b.height / b.width).toInt().coerceIn(4, 32)
        val s = Bitmap.createScaledBitmap(b, w, h, true)
        val px = IntArray(w * h)
        s.getPixels(px, 0, w, 0, 0, w, h)
        return IntArray(px.size) {
            val c = px[it]
            (Color.red(c) * 30 + Color.green(c) * 59 + Color.blue(c) * 11) / 100
        }
    }

    private fun diff(a: IntArray, b: IntArray): Int {
        if (a.size != b.size) return 255
        var sum = 0L
        for (i in a.indices) sum += abs(a[i] - b[i])
        return (sum / a.size).toInt()
    }
}
