package com.fishyu.translate

import android.content.ClipboardManager
import android.content.Intent
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.FrameLayout
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.cancel

class TranslateActivity : AppCompatActivity() {
    companion object { const val EXTRA_CLIPBOARD = "clipboard" }

    private val scope = MainScope()
    private lateinit var card: ResultCard
    private var pendingClipboard = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Dictionary.preload(this)
        val sh = resources.displayMetrics.heightPixels
        card = ResultCard(this, scope, (sh * 0.55).toInt()) { finish() }

        val root = FrameLayout(this).apply {
            isClickable = true
            setOnClickListener { finish() }
        }
        val lp = FrameLayout.LayoutParams(
            minOf(resources.displayMetrics.widthPixels - dp(16), dp(560)), ViewGroup.LayoutParams.WRAP_CONTENT,
            Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL
        ).apply { bottomMargin = dp(16) }
        card.isClickable = true
        root.addView(card, lp)
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets ->
            val b = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
            v.setPadding(0, b.top, 0, b.bottom)
            insets
        }
        setContentView(root)
        handle(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handle(intent)
    }

    private fun handle(i: Intent) {
        val text = when (i.action) {
            Intent.ACTION_PROCESS_TEXT -> i.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)?.toString()
            Intent.ACTION_SEND -> i.getStringExtra(Intent.EXTRA_TEXT)
            else -> null
        }
        if (text != null) {
            card.start(text.trim())
        } else if (i.getBooleanExtra(EXTRA_CLIPBOARD, false)) {
            pendingClipboard = true
            card.showLoading("Đang đọc chữ đã copy...")
            if (hasWindowFocus()) readClipboard()
        } else {
            card.showError("Không có chữ để dịch")
        }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus && pendingClipboard) readClipboard()
    }

    private fun readClipboard() {
        pendingClipboard = false
        val cm = getSystemService(ClipboardManager::class.java)
        val t = cm.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(this)?.toString()
        if (t.isNullOrBlank()) card.showError("Bộ nhớ tạm đang trống. Hãy copy chữ trước.")
        else card.start(t.trim())
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }
}
