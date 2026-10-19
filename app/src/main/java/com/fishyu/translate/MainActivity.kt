package com.fishyu.translate

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.text.method.PasswordTransformationMethod
import android.view.Gravity
import android.view.View
import android.widget.CheckBox
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private val scope = MainScope()
    private lateinit var p: Palette
    private lateinit var col: LinearLayout
    private lateinit var toggleBtn: TextView
    private lateinit var permText: TextView
    private lateinit var keyField: EditText
    private lateinit var usageText: TextView
    private lateinit var domainField: EditText
    private lateinit var glossaryField: EditText

    private val domainPresets = listOf(
        "Y học" to "Medical / clinical text. Use precise standard medical terminology.",
        "Sinh học" to "Biology / life-science text. Use precise scientific terminology.",
        "Tiểu thuyết" to "Chinese web novel / fiction. Natural literary style, keep character names consistent.",
        "Game" to "Video game story dialogue. Natural, casual spoken style; keep character names consistent.",
        "Kỹ thuật" to "Technical documentation. Use precise technical terminology.",
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        p = Palette(this)
        Dictionary.preload(this)

        val scroll = ScrollView(this).apply { setBackgroundColor(p.page) }
        col = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(12), dp(16), dp(40))
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

    private fun card(title: String, tag: String? = null): LinearLayout {
        val c = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = doodle(p, p.bg, dpf(20f), dp(4))
            setPadding(dp(16), dp(12), dp(20), dp(18))
        }
        val head = label(title, 19f, p.fg, bold = true)
        if (tag != null) {
            val t = label(tag, 11f, p.fg).apply {
                typeface = Fonts.medium(this@MainActivity)
                background = rounded(p.accentSoft, dpf(10f), dp(2), p.ink)
                setPadding(dp(8), dp(1), dp(8), dp(2))
            }
            c.addView(hbox(head, spacer(), t))
        } else c.addView(head)
        col.addView(c, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(16) })
        return c
    }

    private fun LinearLayout.text(t: String, color: Int = p.muted, size: Float = 14f) =
        label(t, size, color).apply { setLineSpacing(0f, 1.2f); setPadding(0, dp(2), 0, dp(4)) }.also { addView(it) }

    private fun field(hintText: String, value: String, multi: Boolean = false) = EditText(this).apply {
        setText(value)
        hint = hintText
        textSize = 15f
        setTextColor(p.fg)
        setHintTextColor(p.muted)
        background = rounded(p.surface, dpf(14f), dp(2), p.accentSoft)
        setPadding(dp(12), dp(10), dp(12), dp(10))
        if (multi) {
            minLines = 4
            gravity = Gravity.TOP
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
        }
    }

    private fun LinearLayout.addFull(v: View, top: Int = 8) =
        addView(v, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(top) })

    private fun tint(): ColorStateList = ColorStateList.valueOf(p.accent)

    private fun <T> LinearLayout.radios(items: List<T>, labelOf: (T) -> String, selected: T, horizontal: Boolean = false,
                                        onPick: (T) -> Unit) {
        val g = RadioGroup(this@MainActivity).apply { orientation = if (horizontal) RadioGroup.HORIZONTAL else RadioGroup.VERTICAL }
        items.forEach { item ->
            g.addView(RadioButton(this@MainActivity).apply {
                text = labelOf(item); id = View.generateViewId(); isChecked = item == selected
                setTextColor(p.fg); buttonTintList = tint()
                if (horizontal) setPadding(0, 0, dp(10), 0)
                setOnCheckedChangeListener { _, c -> if (c) onPick(item) }
            })
        }
        addView(g)
    }

    private fun LinearLayout.check(t: String, value: Boolean, onChange: (Boolean) -> Unit) =
        addView(CheckBox(this@MainActivity).apply {
            text = t; isChecked = value; setTextColor(p.fg); buttonTintList = tint()
            setOnCheckedChangeListener { _, c -> onChange(c) }
        })

    private fun build() {
        buildErrorCard()
        buildCoffee()
        buildHero()

        val bubbleCard = card("Bong bóng dịch")
        permText = bubbleCard.text("")
        toggleBtn = bigButton("Bật bong bóng", p) {
            if (BubbleService.running) { BubbleService.stop(this); toggleBtn.postDelayed({ refreshStatus() }, 300) }
            else startBubble()
        }
        bubbleCard.addFull(toggleBtn, 10)

        val liveCard = card("Dịch trực tiếp", "game")
        liveCard.text("Giữ bong bóng, chọn \"Dịch trực tiếp (game)\" rồi khoanh khung thoại. App tự dịch lại mỗi khi chữ trong khung đổi, bạn vẫn chạm vào game bình thường.")
        liveCard.text("Bộ dịch cho chế độ này", p.fg, 14f)
        liveCard.radios(Engine.entries, { if (it == Engine.DEEPL) "DeepL (chuẩn hơn, tốn ký tự)" else "Offline (miễn phí, tiết kiệm)" },
            Prefs.liveEngine) { Prefs.liveEngine = it }
        liveCard.check("Hiện cả chữ gốc trong khung dịch", Prefs.liveShowSource) { Prefs.liveShowSource = it }

        val keyCard = card("DeepL API key")
        keyCard.text("Gói Developer miễn phí của DeepL cho 1 triệu ký tự dùng một lần (không làm mới hằng tháng). Mỗi chữ Hán tính 1 ký tự. Phần gợi ý lĩnh vực và ngữ cảnh không bị tính.")
        keyField = field("Dán DeepL API key vào đây", Prefs.deeplKey).apply {
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            transformationMethod = PasswordTransformationMethod.getInstance()
            isSingleLine = true
            typeface = android.graphics.Typeface.DEFAULT
        }
        keyCard.addFull(keyField)
        usageText = keyCard.text("")
        val show = chip("Hiện", p) {
            val hidden = keyField.transformationMethod != null
            keyField.transformationMethod = if (hidden) null else PasswordTransformationMethod.getInstance()
            (it as TextView).text = if (hidden) "Ẩn" else "Hiện"
        }
        val checkKey = chip("Kiểm tra key", p, filled = true) {
            save()
            usageText.text = "Đang kiểm tra..."
            scope.launch { usageText.text = Translator.deeplUsage() }
        }
        val getKey = chip("Lấy key", p) {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://www.deepl.com/pro-api")))
        }
        keyCard.addView(hbox(checkKey, getKey, show))

        val engineCard = card("Bộ dịch khi khoanh vùng / bôi đen")
        engineCard.radios(Engine.entries, { it.label }, Prefs.engine) { Prefs.engine = it }
        engineCard.check("Tự chuyển sang offline khi DeepL lỗi hoặc hết ký tự", Prefs.fallbackOffline) { Prefs.fallbackOffline = it }

        val langCard = card("Ngôn ngữ nguồn")
        langCard.radios(SourceLang.entries, { it.label }, Prefs.sourceLang, horizontal = true) { Prefs.sourceLang = it }
        langCard.text("Chế độ Tự động nhận ra tiếng Nhật khi có chữ kana (ひらがな/カタカナ). Giữ bong bóng để đổi nhanh.")

        val domainCard = card("Lĩnh vực")
        domainCard.text("Gửi kèm cho DeepL làm ngữ cảnh để chọn từ chuẩn hơn. Nên viết bằng tiếng Anh.")
        domainField = field("Ví dụ: Medical text. Use precise medical terminology.", Prefs.domainHint)
        domainCard.addFull(domainField)
        val presetRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, dp(8), 0, dp(4)) }
        presetRow.addView(chip("Không", p) { domainField.setText("") })
        domainPresets.forEach { (name, hint) ->
            presetRow.addView(chip(name, p) { domainField.setText(hint) },
                LinearLayout.LayoutParams(-2, -2).apply { marginStart = dp(8) })
        }
        domainCard.addView(HorizontalScrollView(this).apply { isHorizontalScrollBarEnabled = false; addView(presetRow) })

        val glossCard = card("Bảng thuật ngữ")
        glossCard.text("Mỗi dòng: chữ gốc = cách dịch cố định. Dùng cho tên nhân vật, thuật ngữ chuyên ngành. Dòng bắt đầu bằng # là ghi chú.")
        glossaryField = field("林动 = Lâm Động\n心肌梗死 = nhồi máu cơ tim\n# ghi chú", Prefs.glossaryText, multi = true)
        glossCard.addFull(glossaryField)

        val testCard = card("Dịch thử")
        val testIn = field("Nhập hoặc dán chữ Trung/Nhật...", "细胞膜是包围细胞质的一层薄膜。")
        testCard.addFull(testIn)
        testCard.addFull(bigButton("Dịch", p) {
            save()
            startActivity(Intent(this, TranslateActivity::class.java)
                .setAction(Intent.ACTION_SEND).putExtra(Intent.EXTRA_TEXT, testIn.text.toString()))
        }, 10)

        val howCard = card("Cách dùng")
        listOf(
            "Chạm bong bóng cá mập, kéo ngón tay để khoanh vùng chữ. Chạm nhẹ vào một đoạn để dịch cả đoạn, hoặc chọn \"Cả màn hình\".",
            "Ở app cho phép chọn chữ: bôi đen rồi chọn \"Dịch (Fishyu)\" (có thể nằm trong mục ba chấm). App không có mục này thì bấm Chép, sau đó giữ bong bóng và chọn \"Dịch chữ đã copy\".",
            "Trong cửa sổ dịch, bôi đen một từ ở phần Bản gốc rồi chọn \"Tra từ\" để xem nghĩa theo ngữ cảnh, pinyin và âm Hán Việt.",
            "Chơi game: giữ bong bóng, chọn \"Dịch trực tiếp (game)\", khoanh khung thoại. Khung dịch kéo được bằng thanh trên cùng, A-/A+ để đổi cỡ chữ, nút DeepL/Offline để đổi bộ dịch.",
            "Thêm nút Fishyu Translate vào thanh cài đặt nhanh để bật tắt cho tiện.",
            "Từ Android 14, khi máy hỏi quyền ghi màn hình hãy chọn \"Toàn bộ màn hình\". Mỗi lần bật bong bóng máy sẽ hỏi lại.",
        ).forEachIndexed { i, s -> howCard.addView(step(i + 1, s)) }

        col.addView(label("Từ điển CC-CEDICT (MDBG, CC BY-SA 4.0). Âm Hán Việt từ Unicode Unihan, chỉ để tham khảo. OCR và dịch offline: Google ML Kit.",
            12f, p.muted).apply { gravity = Gravity.CENTER; setPadding(dp(8), dp(20), dp(8), 0) })
    }

    private fun step(n: Int, s: String): View {
        val num = label("$n", 13f, p.onAccent, bold = true).apply {
            gravity = Gravity.CENTER
            background = rounded(p.accent, dpf(12f), dp(2), p.ink)
        }
        val t = label(s, 14f, p.fg).apply { setLineSpacing(0f, 1.2f) }
        return LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, dp(8), 0, 0)
            addView(num, LinearLayout.LayoutParams(dp(24), dp(24)).apply { topMargin = dp(1) })
            addView(t, LinearLayout.LayoutParams(0, -2, 1f).apply { marginStart = dp(10) })
        }
    }

    private fun buildErrorCard() {
        val log = CrashLog.read(this) ?: return
        lateinit var c: LinearLayout
        c = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = doodle(p, p.bg, dpf(18f), dp(3))
            setPadding(dp(14), dp(10), dp(18), dp(14))
        }
        c.addView(label("App vừa gặp lỗi", 17f, p.error, bold = true))
        c.addView(label("Bấm \"Chép lỗi\" rồi gửi cho người làm app để sửa nhanh hơn.", 13f, p.muted))
        c.addView(label(log.lines().drop(3).take(6).joinToString("\n"), 11f, p.fg).apply {
            typeface = android.graphics.Typeface.MONOSPACE
            background = rounded(p.surface, dpf(10f))
            setPadding(dp(8), dp(6), dp(8), dp(6))
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8); bottomMargin = dp(8) })
        c.addView(hbox(
            chip("Chép lỗi", p, filled = true) {
                val cm = getSystemService(android.content.ClipboardManager::class.java)
                cm.setPrimaryClip(android.content.ClipData.newPlainText("Lỗi Fishyu Translate", log))
                android.widget.Toast.makeText(this, "Đã chép nội dung lỗi", android.widget.Toast.LENGTH_SHORT).show()
            },
            chip("Ẩn", p) {
                CrashLog.clear(this)
                col.removeView(c)
            },
        ))
        col.addView(c, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(4); bottomMargin = dp(12) })
    }

    private fun buildCoffee() {
        val cup = ImageView(this).apply { setImageResource(R.drawable.ic_coffee) }
        val texts = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(label("Buy me a coffee", 17f, p.fg, bold = true))
            addView(label("Thấy app hữu ích thì ủng hộ mình một ly cà phê qua MoMo nhé", 13f, p.muted))
        }
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            background = doodle(p, p.bg, dpf(18f), dp(3))
            setPadding(dp(10), dp(8), dp(16), dp(11))
            isClickable = true
            setOnClickListener { showCoffee() }
            addView(cup, LinearLayout.LayoutParams(dp(44), dp(44)))
            addView(texts, LinearLayout.LayoutParams(0, -2, 1f).apply { marginStart = dp(10) })
            addView(chip("Ủng hộ", p, filled = true) { showCoffee() })
        }
        col.addView(bar, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(4) })
    }

    private fun showCoffee() {
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(20), dp(18), dp(20), dp(8))
        }
        box.addView(label("Cảm ơn bạn đã ủng hộ!", 18f, p.fg, bold = true).apply { gravity = Gravity.CENTER })
        box.addView(label("Quét mã bằng MoMo hoặc app ngân hàng. Nếu đang dùng chính điện thoại này, bấm \"Lưu mã QR\" rồi mở MoMo, chọn quét mã từ ảnh.",
            13f, p.muted).apply { gravity = Gravity.CENTER; setPadding(0, dp(4), 0, dp(10)) })
        box.addView(ImageView(this).apply {
            setImageResource(R.drawable.momo_qr)
            adjustViewBounds = true
        }, LinearLayout.LayoutParams(dp(260), -2))
        val dialog = androidx.appcompat.app.AlertDialog.Builder(this)
            .setView(ScrollView(this).apply { addView(box) })
            .setPositiveButton("Lưu mã QR") { _, _ -> saveQr() }
            .setNeutralButton("Mở MoMo") { _, _ -> openMomo() }
            .setNegativeButton("Đóng", null)
            .create()
        dialog.show()
    }

    private fun saveQr() {
        if (Build.VERSION.SDK_INT < 29) {
            android.widget.Toast.makeText(this, "Máy này chưa hỗ trợ lưu tự động, hãy chụp màn hình mã QR", android.widget.Toast.LENGTH_LONG).show()
            return
        }
        try {
            val values = android.content.ContentValues().apply {
                put(android.provider.MediaStore.Images.Media.DISPLAY_NAME, "fishyu_momo_qr.jpg")
                put(android.provider.MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
                put(android.provider.MediaStore.Images.Media.RELATIVE_PATH, "Pictures/Fishyu")
            }
            val uri = contentResolver.insert(android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
                ?: throw IllegalStateException()
            val bmp = android.graphics.BitmapFactory.decodeResource(resources, R.drawable.momo_qr)
            contentResolver.openOutputStream(uri).use { out ->
                bmp.compress(android.graphics.Bitmap.CompressFormat.JPEG, 95, out!!)
            }
            android.widget.Toast.makeText(this, "Đã lưu vào Ảnh > Pictures/Fishyu", android.widget.Toast.LENGTH_LONG).show()
        } catch (e: Exception) {
            android.widget.Toast.makeText(this, "Không lưu được ảnh", android.widget.Toast.LENGTH_SHORT).show()
        }
    }

    private fun openMomo() {
        val i = packageManager.getLaunchIntentForPackage("com.mservice.momotransfer")
        if (i != null) startActivity(i)
        else startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=com.mservice.momotransfer")))
    }

    private fun buildHero() {
        val hero = FrameLayout(this).apply {
            background = doodle(p, p.accentSoft, dpf(24f), dp(4))
        }
        val inner = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(16), dp(18), dp(20), dp(10))
        }
        inner.addView(ImageView(this).apply { setImageResource(R.drawable.mascot_shark) },
            LinearLayout.LayoutParams(dp(150), dp(128)))
        inner.addView(label("Fishyu Translate", 28f, p.fg, bold = true).apply { gravity = Gravity.CENTER })
        inner.addView(label("Đọc truyện, tài liệu, chơi game tiếng Trung - Nhật bằng tiếng Việt", 14f, p.fg).apply {
            gravity = Gravity.CENTER
            alpha = 0.8f
        })
        inner.addView(WaveView(this, p), LinearLayout.LayoutParams(dp(180), dp(14)).apply { topMargin = dp(10) })
        hero.addView(inner)
        col.addView(hero, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8) })
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

private class WaveView(ctx: Context, private val p: Palette) : View(ctx) {
    private val line = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = p.accent; style = Paint.Style.STROKE; strokeWidth = ctx.dpf(3f); strokeCap = Paint.Cap.ROUND
    }
    private val path = Path()

    override fun onDraw(c: Canvas) {
        val w = width.toFloat(); val h = height.toFloat()
        val step = context.dpf(36f)
        path.reset()
        path.moveTo(0f, h * 0.5f)
        var x = 0f
        var up = true
        while (x < w) {
            path.quadTo(x + step / 2, if (up) 0f else h, x + step, h * 0.5f)
            x += step; up = !up
        }
        c.drawPath(path, line)
    }
}
