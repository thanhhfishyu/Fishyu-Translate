package com.fishyu.translate

import android.content.Context
import android.os.Build
import java.io.File
import java.io.PrintWriter
import java.io.StringWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object CrashLog {
    private fun file(ctx: Context) = File(ctx.filesDir, "last_error.txt")

    fun install(ctx: Context) {
        val app = ctx.applicationContext
        val prev = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { t, e ->
            runCatching { save(app, e, "crash") }
            prev?.uncaughtException(t, e)
        }
    }

    fun save(ctx: Context, e: Throwable, where: String) {
        val sw = StringWriter()
        e.printStackTrace(PrintWriter(sw))
        val ver = runCatching {
            ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName
        }.getOrNull()
        val text = buildString {
            append("Fishyu Translate ").append(ver).append('\n')
            append(SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date())).append('\n')
            append(Build.MANUFACTURER).append(' ').append(Build.MODEL)
                .append(" - Android ").append(Build.VERSION.RELEASE).append(" (API ").append(Build.VERSION.SDK_INT).append(")\n")
            append("Vị trí: ").append(where).append("\n\n")
            append(sw.toString().take(6000))
        }
        runCatching { file(ctx).writeText(text) }
    }

    fun read(ctx: Context): String? = runCatching { file(ctx).takeIf { it.exists() }?.readText() }.getOrNull()

    fun clear(ctx: Context) { runCatching { file(ctx).delete() } }

    fun shortReason(e: Throwable): String {
        val msg = e.message ?: e.javaClass.simpleName
        return when {
            e is SecurityException -> "Hệ thống từ chối quyền chụp màn hình ($msg)"
            else -> msg
        }.take(160)
    }
}
