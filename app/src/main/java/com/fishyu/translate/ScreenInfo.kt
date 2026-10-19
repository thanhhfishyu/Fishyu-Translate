package com.fishyu.translate

import android.content.Context
import android.hardware.display.DisplayManager
import android.os.Build
import android.util.DisplayMetrics
import android.view.Display
import android.view.WindowManager

object ScreenInfo {
    data class Size(val width: Int, val height: Int, val dpi: Int)

    fun get(ctx: Context): Size {
        val dpi = ctx.resources.displayMetrics.densityDpi
        if (Build.VERSION.SDK_INT >= 30) {
            runCatching {
                val b = ctx.getSystemService(WindowManager::class.java).maximumWindowMetrics.bounds
                if (b.width() > 0 && b.height() > 0) return Size(b.width(), b.height(), dpi)
            }
        }
        runCatching {
            val d = ctx.getSystemService(DisplayManager::class.java).getDisplay(Display.DEFAULT_DISPLAY)
            val m = DisplayMetrics()
            @Suppress("DEPRECATION") d.getRealMetrics(m)
            if (m.widthPixels > 0 && m.heightPixels > 0) return Size(m.widthPixels, m.heightPixels, dpi)
        }
        val m = ctx.resources.displayMetrics
        return Size(m.widthPixels.coerceAtLeast(1), m.heightPixels.coerceAtLeast(1), dpi)
    }
}
