package com.fishyu.translate

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.PixelFormat
import android.graphics.Rect
import android.hardware.input.InputManager
import android.os.Build
import android.os.SystemClock
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import com.google.mlkit.vision.text.Text
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

object ReplaceLayout {
    fun isCjk(s: String) = Dictionary.hanCount(s) > 0 || Dictionary.hasKana(s)

    fun pieces(t: Text): List<Piece> = t.textBlocks.mapNotNull { b ->
        val box = b.boundingBox ?: return@mapNotNull null
        val src = OcrEngine.assembleBlock(b)
        if (!isCjk(src)) return@mapNotNull null
        Piece(Rect(box), b.lines.mapNotNull { l -> l.boundingBox?.let { Rect(it) } }, src)
    }.sortedWith(compareBy({ it.box.top }, { it.box.left }))

    fun key(pieces: List<Piece>) = pieces.joinToString("\n") { it.source }
}

class ReplaceSession(
    private val ctx: Context,
    private val appWm: WindowManager,
    private val scope: CoroutineScope,
    private val capturer: ScreenCapturer,
    private val onBusy: (Boolean) -> Unit,
    private val onMessage: (String) -> Unit,
) {
    private class Layer(ctx: Context) : View(ctx) {
        var bitmap: Bitmap? = null
        private val loc = IntArray(2)
        override fun onDraw(c: Canvas) {
            val b = bitmap ?: return
            getLocationOnScreen(loc)
            c.drawBitmap(b, -loc[0].toFloat(), -loc[1].toFloat(), null)
        }
    }

    private val gate = ReplaceGate()
    private var layer: Layer? = null
    private var layerWm: WindowManager? = null
    private var layerLp: WindowManager.LayoutParams? = null
    var trusted = false
        private set
    private var watcher: View? = null
    private var loop: Job? = null
    private var work: Job? = null
    private var paused = false
    private var visible = false
    private var hideAt = 0L
    private var hideFrame = 0L
    private var showFrame = 0L
    private var op = 0
    private var lastBitmap: Bitmap? = null
    private var lastNote: String? = null
    private val cell get() = (capturer.width / 36).coerceAtLeast(16)
    private val main = android.os.Handler(android.os.Looper.getMainLooper())
    private var showAt = 0L

    fun start() {
        attachLayer()
        attachWatcher()
        OverlayAccess.onChanged = { main.post { if (loop?.isActive == true) reattach() } }
        loop = scope.launch { run() }
    }

    fun stop() {
        loop?.cancel(); work?.cancel()
        if (OverlayAccess.onChanged != null) OverlayAccess.onChanged = null
        detachLayer()
        watcher?.let { runCatching { appWm.removeView(it) } }
        watcher = null
        onBusy(false)
    }

    fun setPaused(p: Boolean) {
        if (paused == p) return
        paused = p
        if (p) {
            op++; work?.cancel()
            hide()
        }
        gate.reset(now())
    }

    fun refresh() {
        op++; work?.cancel()
        hide()
        gate.reset(now())
    }

    fun onConfigChanged() {
        op++; work?.cancel()
        lastBitmap = null
        reattach()
        gate.reset(now())
    }

    private fun now() = SystemClock.uptimeMillis()

    private fun reattach() {
        val wasVisible = visible
        detachLayer()
        attachLayer()
        if (wasVisible && lastBitmap != null && gate.state == ReplaceGate.State.SHOWN) show(lastBitmap!!)
    }

    private fun attachLayer() {
        val accWm = OverlayAccess.windowManager()
        val wm = accWm ?: appWm
        val type = if (accWm != null) WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY
        else WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        val lp = WindowManager.LayoutParams(
            capturer.width, capturer.height, type,
            WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE or WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            if (Build.VERSION.SDK_INT >= 28) layoutInDisplayCutoutMode =
                if (Build.VERSION.SDK_INT >= 30) WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
                else WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
            alpha = if (accWm != null) 1f else passThroughAlpha(ctx)
        }
        val v = Layer(ctx).apply { visibility = View.GONE }
        try {
            wm.addView(v, lp)
        } catch (e: Throwable) {
            if (accWm == null) throw e
            lp.type = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            lp.alpha = passThroughAlpha(ctx)
            appWm.addView(v, lp)
            layer = v; layerWm = appWm; layerLp = lp; trusted = false
            gate.peekOnTouch = false
            return
        }
        layer = v; layerWm = wm; layerLp = lp
        trusted = accWm != null
        gate.peekOnTouch = trusted
        visible = false
    }

    private fun detachLayer() {
        val v = layer ?: return
        runCatching { layerWm?.removeView(v) }
        layer = null; layerWm = null; layerLp = null
        visible = false
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun attachWatcher() {
        val v = View(ctx)
        val lp = WindowManager.LayoutParams(
            1, 1, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply { gravity = Gravity.TOP or Gravity.START; x = 0; y = 0 }
        v.setOnTouchListener { _, e ->
            if (e.actionMasked == MotionEvent.ACTION_OUTSIDE) touched()
            false
        }
        if (runCatching { appWm.addView(v, lp) }.isSuccess) watcher = v
    }

    fun touched() {
        val before = gate.state
        gate.touch(now())
        if (before == ReplaceGate.State.BUSY && gate.state != before) { op++; work?.cancel(); onBusy(false) }
    }

    private fun show(b: Bitmap) {
        val v = layer ?: return
        v.bitmap = b
        v.visibility = View.VISIBLE
        v.invalidate()
        visible = true
        showAt = now()
        showFrame = capturer.frames
    }

    private fun hide() {
        val v = layer ?: return
        if (v.visibility != View.GONE) v.visibility = View.GONE
        if (visible) {
            visible = false
            hideAt = now()
            hideFrame = capturer.frames
        }
    }

    private fun cleanFrameReady(): Boolean =
        now() - hideAt >= 120 && (capturer.frames > hideFrame || now() - hideAt > 1500)

    private suspend fun run() {
        while (scope.isActive) {
            delay(160)
            if (paused || capturer.width <= 0) continue
            if (!visible && !cleanFrameReady()) continue
            val sig = withContext(Dispatchers.Default) { capturer.signature(cell) } ?: continue
            if (visible && gate.needsReference) {
                if (now() - showAt >= 150 && (sig.frame > showFrame || now() - showAt > 1500)) gate.reference(sig)
                continue
            }
            when (gate.frame(sig, now())) {
                ReplaceGate.Action.HIDE -> hide()
                ReplaceGate.Action.PEEK -> hide()
                ReplaceGate.Action.SHOW_CACHED -> lastBitmap?.let { show(it) } ?: gate.reset(now())
                ReplaceGate.Action.PROCESS -> process(sig)
                ReplaceGate.Action.NONE -> Unit
            }
        }
    }

    private fun process(sig: ScreenSig) {
        val my = ++op
        work = scope.launch {
            onBusy(true)
            try {
                val full = withContext(Dispatchers.Default) {
                    capturer.grabRegion(Rect(0, 0, capturer.width, capturer.height))
                } ?: run { gate.failed(now(), 800); return@launch }
                val (text, lang) = OcrEngine.raw(full)
                if (my != op) return@launch
                val pieces = ReplaceLayout.pieces(text)
                if (!gate.ocrDone(ReplaceLayout.key(pieces), now())) return@launch
                if (pieces.isEmpty()) {
                    gate.processed(sig, null)
                    return@launch
                }
                val page = pieces.joinToString("\n") { it.source }
                val res = Translator.translateMany(pieces.map { it.source }, lang, page, Prefs.replaceEngine)
                if (my != op) return@launch
                pieces.forEachIndexed { i, p -> p.text = res[i].text }
                val density = ctx.resources.displayMetrics.density
                val out = withContext(Dispatchers.Default) { ReplaceRenderer.render(full, pieces, density) }
                if (my != op) return@launch
                val again = withContext(Dispatchers.Default) { capturer.signature(cell) }
                if (again != null && ScreenSig.changed(sig, again, 8) > 0.01f) {
                    gate.abort(now())
                    return@launch
                }
                if (out.painted.isEmpty()) {
                    gate.processed(sig, null)
                    return@launch
                }
                lastBitmap = out.bitmap
                gate.processed(sig, sig.zoneOf(out.painted, cell))
                show(out.bitmap)
                val note = res.firstNotNullOfOrNull { it.note }
                if (note != null && note != lastNote) { lastNote = note; onMessage(note) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: TranslateException) {
                if (my == op) {
                    gate.failed(now())
                    onMessage("Lỗi dịch: ${e.message}")
                }
            } catch (e: Exception) {
                if (my == op) {
                    gate.failed(now())
                    CrashLog.save(ctx, e, "replace")
                }
            } finally {
                if (my == op) onBusy(false)
            }
        }
    }

    companion object {
        fun passThroughAlpha(ctx: Context): Float {
            if (Build.VERSION.SDK_INT < 31) return 1f
            val max = runCatching { ctx.getSystemService(InputManager::class.java).maximumObscuringOpacityForTouch }
                .getOrDefault(0.8f)
            return (max - 0.01f).coerceIn(0.5f, 1f)
        }
    }
}
