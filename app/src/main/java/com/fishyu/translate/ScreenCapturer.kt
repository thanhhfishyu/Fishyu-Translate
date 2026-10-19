package com.fishyu.translate

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.graphics.Rect
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.os.Handler
import android.os.HandlerThread
import android.util.DisplayMetrics
import android.view.WindowManager
import kotlinx.coroutines.delay
import java.nio.ByteBuffer

class ScreenCapturer(private val ctx: Context, private val projection: MediaProjection, onStopped: () -> Unit) {
    private val thread = HandlerThread("capture").apply { start() }
    private val handler = Handler(thread.looper)
    private var reader: ImageReader? = null
    private var display: VirtualDisplay? = null
    @Volatile private var latest: Image? = null
    @Volatile private var frameCounter = 0L
    private val lock = Any()
    @Volatile private var released = false
    private var displayW = 0
    private var displayH = 0
    var width = 0; private set
    var height = 0; private set

    init {
        projection.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() {
                val wasOurs = released
                release()
                if (!wasOurs) onStopped()
            }
        }, handler)
        val (w, h, dpi) = metrics()
        width = w; height = h
        displayW = w; displayH = h
        val r = newReader(w, h)
        reader = r
        display = projection.createVirtualDisplay(
            "fishyu-translate", w, h, dpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, r.surface, null, handler
        )
    }

    @SuppressLint("WrongConstant")
    private fun newReader(w: Int, h: Int): ImageReader =
        ImageReader.newInstance(w, h, PixelFormat.RGBA_8888, 3).apply {
            setOnImageAvailableListener({ rd ->
                val img = try { rd.acquireLatestImage() } catch (e: Exception) { null } ?: return@setOnImageAvailableListener
                synchronized(lock) {
                    if (rd !== reader) { img.close(); return@setOnImageAvailableListener }
                    latest?.close()
                    latest = img
                    frameCounter++
                }
            }, handler)
        }

    private fun metrics(): Triple<Int, Int, Int> {
        val wm = ctx.getSystemService(WindowManager::class.java)
        val dm = ctx.resources.displayMetrics
        return if (android.os.Build.VERSION.SDK_INT >= 30) {
            val b = wm.maximumWindowMetrics.bounds
            Triple(b.width(), b.height(), dm.densityDpi)
        } else {
            val real = DisplayMetrics()
            @Suppress("DEPRECATION") wm.defaultDisplay.getRealMetrics(real)
            Triple(real.widthPixels, real.heightPixels, real.densityDpi)
        }
    }

    fun onConfigChanged() {
        val (w, h, dpi) = metrics()
        if (w == width && h == height) return
        swapSurface(w, h, dpi)
    }

    private fun swapSurface(w: Int, h: Int, dpi: Int): Boolean {
        if (released) return false
        val old = reader
        val r = newReader(w, h)
        try {
            if (w != displayW || h != displayH) {
                display?.resize(w, h, dpi)
                displayW = w; displayH = h
            }
            display?.surface = r.surface
        } catch (e: Throwable) {
            CrashLog.save(ctx, e, "swapSurface")
            runCatching { r.close() }
            return false
        }
        synchronized(lock) {
            latest?.close(); latest = null
            width = w; height = h
            reader = r
        }
        handler.postDelayed({ runCatching { old?.close() } }, 300)
        return true
    }

    suspend fun capture(start: Long = frameCounter): Bitmap? {
        val (w, h, _) = metrics()
        if (w != width || h != height) onConfigChanged()
        if (waitFrameAfter(start, 900)) {
            delay(60)
            synchronized(lock) { latest?.let { return toBitmap(it) } }
        }
        val (w2, h2, dpi) = metrics()
        val before = frameCounter
        if (swapSurface(w2, h2, dpi) && waitFrameAfter(before, 900)) {
            synchronized(lock) { latest?.let { return toBitmap(it) } }
        }
        return null
    }

    private suspend fun waitFrameAfter(start: Long, timeoutMs: Int): Boolean {
        var t = 0
        while (t < timeoutMs) {
            if (frameCounter > start) return true
            delay(30); t += 30
        }
        return frameCounter > start
    }

    val frames: Long get() = frameCounter

    fun grabRegion(r: Rect): Bitmap? = synchronized(lock) {
        val img = latest ?: return null
        val left = r.left.coerceIn(0, img.width - 1)
        val top = r.top.coerceIn(0, img.height - 1)
        val right = r.right.coerceIn(left + 1, img.width)
        val bottom = r.bottom.coerceIn(top + 1, img.height)
        val w = right - left
        val h = bottom - top
        val plane = img.planes[0]
        val src = plane.buffer
        val rowStride = plane.rowStride
        val ps = plane.pixelStride
        val out = ByteBuffer.allocateDirect(w * h * 4)
        val row = ByteArray(w * ps)
        for (y in 0 until h) {
            src.position((top + y) * rowStride + left * ps)
            src.get(row, 0, w * ps)
            out.put(row, 0, w * 4)
        }
        out.rewind()
        Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888).apply { copyPixelsFromBuffer(out) }
    }

    private fun toBitmap(img: Image): Bitmap {
        val plane = img.planes[0]
        val buf = plane.buffer
        buf.rewind()
        val pixelStride = plane.pixelStride
        val rowPadding = plane.rowStride - pixelStride * img.width
        val bmp = Bitmap.createBitmap(img.width + rowPadding / pixelStride, img.height, Bitmap.Config.ARGB_8888)
        bmp.copyPixelsFromBuffer(buf)
        return if (bmp.width != img.width) Bitmap.createBitmap(bmp, 0, 0, img.width, img.height) else bmp
    }

    fun release() {
        if (released && display == null) return
        released = true
        synchronized(lock) { latest?.close(); latest = null }
        runCatching { display?.release() }
        runCatching { reader?.close() }
        display = null; reader = null
        thread.quitSafely()
    }
}
