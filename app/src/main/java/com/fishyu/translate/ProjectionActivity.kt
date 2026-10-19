package com.fishyu.translate

import android.app.Activity
import android.content.Intent
import android.media.projection.MediaProjectionConfig
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.core.content.ContextCompat

class ProjectionActivity : Activity() {
    private val req = 42
    private var handled = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!Settings.canDrawOverlays(this)) {
            Toast.makeText(this, "Hãy cho phép \"Hiển thị trên ứng dụng khác\" cho Fishyu Translate", Toast.LENGTH_LONG).show()
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            finish()
            return
        }
        if (savedInstanceState != null) return
        val mpm = getSystemService(MediaProjectionManager::class.java)
        @Suppress("DEPRECATION")
        val consent = if (Build.VERSION.SDK_INT >= 34) {
            runCatching { mpm.createScreenCaptureIntent(MediaProjectionConfig.createConfigForDefaultDisplay()) }
                .getOrElse { mpm.createScreenCaptureIntent() }
        } else mpm.createScreenCaptureIntent()
        try {
            startActivityForResult(consent, req)
        } catch (e: Throwable) {
            CrashLog.save(this, e, "consent")
            Toast.makeText(this, "Không mở được hộp thoại cấp quyền chụp màn hình", Toast.LENGTH_LONG).show()
            finish()
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == req) {
            if (resultCode == RESULT_OK && data != null && !handled) {
                handled = true
                ContextCompat.startForegroundService(this,
                    Intent(this, BubbleService::class.java)
                        .setAction(BubbleService.ACTION_START)
                        .putExtra(BubbleService.EXTRA_CODE, resultCode)
                        .putExtra(BubbleService.EXTRA_DATA, data)
                        .putExtra(BubbleService.EXTRA_TOKEN, System.nanoTime())
                        .putExtra(BubbleService.EXTRA_THEN, intent.getIntExtra(BubbleService.EXTRA_THEN, 0)))
                Toast.makeText(this, "Đã bật bong bóng. Chạm vào nó để dịch.", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(this, "Cần quyền chụp màn hình để dịch bằng bong bóng", Toast.LENGTH_SHORT).show()
            }
        }
        finish()
    }
}
