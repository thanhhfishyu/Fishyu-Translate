package com.fishyu.translate

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private val scope = MainScope()
    private lateinit var p: Palette
    private lateinit var col: LinearLayout
    private lateinit var toggleBtn: MaterialButton
    private lateinit var permText: TextView
    private lateinit var keyField: TextInputEditText
    private lateinit var usageText: TextView
    private lateinit var domainField: EditText
    private lateinit var glossaryField: EditText

    private val domainPresets = listOf(
        "Y học" to "Medical / clinical text. Use precise standard medical terminology.",
        "Sinh học" to "Biology / life-science text. Use precise scientific terminology.",
        "Tiểu thuyết" to "Chinese web novel / fiction. Natural literary style, keep character names consistent.",
        "Kỹ thuật" to "Technical documentation. Use precise technical terminology.",
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        p = Palette(this)
        Dictionary.preload(this)

        val scroll = ScrollView(this).apply { setBackgroundColor(p.bg) }
        col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(20), dp(20), dp(40))
        }
        scroll.addView(col)
        ViewCompat.setOnApplyWindowInsetsListener(scroll) { v, insets ->
            val b = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.ime())
            v.setPadding(b.left, b.top, b.right, b.bottom); insets
        }
        setContentView(scroll)
        build()
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
    }

    override fun onPause() {
        super.onPause()
        save()
    }

    override fun onDestroy() { scope.cancel(); super.onDestroy() }

    private fun save() {
        Prefs.deeplKey = keyField.text?.toString() ?: ""
        Prefs.domainHint = domainField.text.toString()
        Prefs.glossaryText = glossaryField.text.toString()
    }

    private fun title(t: String) = col.addView(label(t, 18f, p.fg, bold = true).apply {
        setPadding(0, dp(24), 0, dp(6))
    })

    private fun body(t: String, color: Int = p.muted, size: Float = 14f) = label(t, size, color).apply {
        setLineSpacing(0f, 1.2f)
    }.also { col.addView(it) }

    private fun button(t: String, filled: Boolean = true, onClick: () -> Unit) =
        MaterialButton(this, null,
            if (filled) com.google.android.material.R.attr.materialButtonStyle
            else com.google.android.material.R.attr.materialButtonOutlinedStyle).apply {
            text = t
            setOnClickListener { onClick() }
        }

    private fun build() {
        col.addView(label("Fishyu Translate", 26f, p.fg, bold = true))
        body("Dịch tiếng Trung / tiếng Nhật trên màn hình sang tiếng Việt, theo ngữ cảnh bằng DeepL.")

        title("Bong bóng dịch")
        permText = body("")
        toggleBtn = button("Bật bong bóng") {
            if (BubbleService.running) { BubbleService.stop(this); toggleBtn.postDelayed({ refreshStatus() }, 300) }
            else startBubble()
        }
        col.addView(toggleBtn, LinearLayout.LayoutParams(-1, dp(52)).apply { topMargin = dp(8) })

        title("DeepL API key")
        body("Key miễn phí có 500.000 ký tự/tháng (key dạng ...:fx). Mỗi chữ Hán tính là 1 ký tự.")
        val til = TextInputLayout(this).apply {
            hint = "Dán DeepL API key vào đây"
            endIconMode = TextInputLayout.END_ICON_PASSWORD_TOGGLE
        }
        keyField = TextInputEditText(til.context).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            setText(Prefs.deeplKey)
        }
        til.addView(keyField)
        col.addView(til, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8) })
        usageText = body("")
        val check = button("Kiểm tra key", filled = false) {
            save()
            usageText.text = "Đang kiểm tra..."
            scope.launch { usageText.text = Translator.deeplUsage() }
        }
        val getKey = button("Lấy key miễn phí", filled = false) {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://www.deepl.com/pro-api")))
        }
        col.addView(hbox(check, getKey))

        title("Bộ dịch")
        val engineGroup = RadioGroup(this)
        Engine.entries.forEach { e ->
            engineGroup.addView(RadioButton(this).apply {
                text = e.label; id = View.generateViewId(); isChecked = Prefs.engine == e
                setOnCheckedChangeListener { _, c -> if (c) Prefs.engine = e }
            })
        }
        col.addView(engineGroup)
        col.addView(CheckBox(this).apply {
            text = "Tự chuyển sang dịch offline khi DeepL lỗi hoặc hết quota"
            isChecked = Prefs.fallbackOffline
            setOnCheckedChangeListener { _, c -> Prefs.fallbackOffline = c }
        })

        title("Ngôn ngữ nguồn")
        val langGroup = RadioGroup(this).apply { orientation = RadioGroup.HORIZONTAL }
        SourceLang.entries.forEach { l ->
            langGroup.addView(RadioButton(this).apply {
                text = l.label; id = View.generateViewId(); isChecked = Prefs.sourceLang == l
                setPadding(0, 0, dp(12), 0)
                setOnCheckedChangeListener { _, c -> if (c) Prefs.sourceLang = l }
            })
        }
        col.addView(langGroup)
        body("Chế độ Tự động nhận ra tiếng Nhật khi có chữ kana (ひらがな/カタカナ). Có thể đổi nhanh bằng cách giữ bong bóng.")

        title("Lĩnh vực (gợi ý ngữ cảnh cho DeepL)")
        body("Câu này được gửi kèm làm ngữ cảnh, không tính vào quota. Nên viết bằng tiếng Anh.")
        domainField = EditText(this).apply {
            setText(Prefs.domainHint)
            hint = "Ví dụ: Medical text. Use precise medical terminology."
            textSize = 14f
        }
        col.addView(domainField, LinearLayout.LayoutParams(-1, -2))
        val presetRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val hs = android.widget.HorizontalScrollView(this).apply { isHorizontalScrollBarEnabled = false; addView(presetRow) }
        presetRow.addView(chip("Không", p) { domainField.setText("") })
        domainPresets.forEach { (name, hint) ->
            presetRow.addView(chip(name, p) { domainField.setText(hint) },
                LinearLayout.LayoutParams(-2, -2).apply { marginStart = dp(8) })
        }
        col.addView(hs, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(6) })

        title("Bảng thuật ngữ")
        body("Mỗi dòng: chữ gốc = cách dịch cố định. Dùng cho tên nhân vật, thuật ngữ y/sinh học... Dòng bắt đầu bằng # là ghi chú.")
        glossaryField = EditText(this).apply {
            setText(Prefs.glossaryText)
            hint = "林动 = Lâm Động\n心肌梗死 = nhồi máu cơ tim\n# ghi chú"
            minLines = 4
            gravity = Gravity.TOP
            textSize = 15f
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
        }
        col.addView(glossaryField, LinearLayout.LayoutParams(-1, -2))

        title("Dịch thử")
        val testIn = EditText(this).apply {
            hint = "Nhập hoặc dán chữ Trung/Nhật..."
            setText("细胞膜是包围细胞质的一层薄膜。")
            textSize = 15f
        }
        col.addView(testIn, LinearLayout.LayoutParams(-1, -2))
        col.addView(button("Dịch") {
            save()
            startActivity(Intent(this, TranslateActivity::class.java)
                .setAction(Intent.ACTION_SEND).putExtra(Intent.EXTRA_TEXT, testIn.text.toString()))
        }, LinearLayout.LayoutParams(-2, -2).apply { topMargin = dp(6) })

        title("Cách dùng")
        body("""
            1. Khoanh vùng: chạm bong bóng 译 -> kéo ngón tay khoanh vùng chữ. Hoặc chạm nhẹ vào một đoạn để dịch nguyên đoạn đó, hoặc bấm "Cả màn hình".
            2. Bôi đen chữ: ở app cho phép chọn chữ, bôi đen -> chọn "Dịch (Fishyu)" trong menu (có thể nằm trong mục ba chấm). Nếu app không có mục này, bấm "Chép" rồi giữ bong bóng -> "Dịch chữ đã copy".
            3. Trong cửa sổ dịch: bôi đen một từ ở phần "Bản gốc" -> "Tra từ" để xem nghĩa theo ngữ cảnh, pinyin, âm Hán Việt.
            4. Giữ bong bóng để mở menu: đổi ngôn ngữ, dịch chữ đã copy, tắt bong bóng. Kéo bong bóng để di chuyển.
            5. Có thể thêm nút "Fishyu Translate" vào thanh cài đặt nhanh (kéo thanh thông báo xuống -> bút chì) để bật/tắt nhanh.

            Android 14 trở lên: khi xin quyền ghi màn hình, chọn "Toàn bộ màn hình" (không chọn "Một ứng dụng"). Mỗi lần bật bong bóng hệ thống sẽ hỏi lại - đây là quy định của Android.
        """.trimIndent(), p.fg)

        title("Nguồn dữ liệu")
        body("Từ điển CC-CEDICT (MDBG, giấy phép CC BY-SA 4.0). Âm Hán Việt từ Unicode Unihan (kVietnamese), chỉ mang tính tham khảo. OCR và dịch offline bởi Google ML Kit.", size = 12f)
    }

    private fun refreshStatus() {
        val overlay = Settings.canDrawOverlays(this)
        val notif = Build.VERSION.SDK_INT < 33 ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        permText.text = buildString {
            append(if (overlay) "Đã cấp: hiển thị trên ứng dụng khác\n" else "Chưa cấp: hiển thị trên ứng dụng khác\n")
            append(if (notif) "Đã cấp: thông báo" else "Chưa cấp: thông báo (cần để bong bóng chạy ổn định)")
        }
        toggleBtn.text = if (BubbleService.running) "Tắt bong bóng" else "Bật bong bóng"
    }

    private fun startBubble() {
        save()
        if (!Settings.canDrawOverlays(this)) {
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
            return
        }
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 7)
            return
        }
        startActivity(Intent(this, ProjectionActivity::class.java))
    }

    @Deprecated("Deprecated in Java")
    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        @Suppress("DEPRECATION")
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        refreshStatus()
        if (requestCode == 7) startActivity(Intent(this, ProjectionActivity::class.java))
    }
}
