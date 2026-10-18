package com.fishyu.translate

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.PixelFormat
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

class ScreenCapturer(private val ctx: Context, private val projection: MediaProjection, onStopped: () -> Unit) {
    private val thread = HandlerThread("capture").apply { start() }
    private val handler = Handler(thread.looper)
    private var reader: ImageReader? = null
    private var display: VirtualDisplay? = null
    @Volatile private var latest: Image? = null
    @Volatile private var frameCounter = 0L
    private val lock = Any()
    var width = 0; private set
    var height = 0; private set

    init {
        projection.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() { release(); onStopped() }
        }, handler)
        val (w, h, dpi) = metrics()
        width = w; height = h
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
        width = w; height = h
        val old = reader
        val r = newReader(w, h)
        reader = r
        display?.resize(w, h, dpi)
        display?.surface = r.surface
        synchronized(lock) { latest?.close(); latest = null }
        handler.post { old?.close() }
    }

    suspend fun capture(): Bitmap? {
        val start = frameCounter
        delay(120)
        var waited = 0
        while (frameCounter == start && waited < 480) { delay(40); waited += 40 }
        return synchronized(lock) { latest?.let { toBitmap(it) } }
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
        synchronized(lock) { latest?.close(); latest = null }
        runCatching { display?.release() }
        runCatching { reader?.close() }
        display = null; reader = null
        thread.quitSafely()
    }
}
