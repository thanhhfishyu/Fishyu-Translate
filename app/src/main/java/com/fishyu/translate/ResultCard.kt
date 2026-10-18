package com.fishyu.translate

import android.annotation.SuppressLint
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.text.InputType
import android.util.TypedValue
import android.view.ActionMode
import android.view.Gravity
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

@SuppressLint("ViewConstructor")
class ResultCard(
    ctx: Context,
    private val scope: CoroutineScope,
    private val maxHeightPx: Int,
    private val onClose: () -> Unit,
) : LinearLayout(ctx) {

    private val p = Palette(ctx)
    val header: LinearLayout
    private val langChip: TextView
    private val engineLabel: TextView
    private val translation: TextView
    private val note: TextView
    private val source: EditText
    private val dictBox: LinearLayout
    private var lang: SourceLang = Prefs.sourceLang
    private var paraContext: String? = null
    private var job: Job? = null
    private var lookupJob: Job? = null

    init {
        orientation = VERTICAL
        background = rounded(p.bg, ctx.dpf(18f), ctx.dp(1), p.line)
        elevation = ctx.dpf(8f)
        val pad = ctx.dp(14)
        setPadding(pad, ctx.dp(10), pad, pad)

        langChip = ctx.chip(lang.label, p) { cycleLang() }
        engineLabel = ctx.label("", 12f, p.muted)
        val copy = ctx.chip("Chép", p) { copyTranslation() }
        val close = ctx.chip("Đóng", p) { onClose() }
        header = ctx.hbox(langChip, engineLabel, ctx.spacer(), copy, close)
        addView(header, LayoutParams(-1, -2))

        val content = LinearLayout(ctx).apply { orientation = VERTICAL }

        translation = ctx.label("", 17f, p.fg).apply {
            setTextIsSelectable(true)
            setLineSpacing(0f, 1.25f)
            setPadding(0, ctx.dp(10), 0, ctx.dp(4))
        }
        content.addView(translation, LayoutParams(-1, -2))

        note = ctx.label("", 12f, p.muted).apply { visibility = GONE }
        content.addView(note, LayoutParams(-1, -2))

        content.addView(View(ctx).apply { setBackgroundColor(p.line) },
            LayoutParams(-1, ctx.dp(1)).apply { topMargin = ctx.dp(10); bottomMargin = ctx.dp(8) })

        val retranslate = ctx.chip("Dịch lại", p) { translateNow(source.text.toString()) }
        val srcTitle = ctx.label("Bản gốc - bôi đen để tra từ, sửa nếu OCR sai", 12f, p.muted)
        content.addView(ctx.hbox(srcTitle, ctx.spacer(), retranslate), LayoutParams(-1, -2))

        source = EditText(ctx).apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            setTextColor(p.fg)
            background = rounded(p.surface, ctx.dpf(10f))
            setPadding(ctx.dp(10), ctx.dp(8), ctx.dp(10), ctx.dp(8))
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or
                InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
            isSingleLine = false
            gravity = Gravity.TOP or Gravity.START
            customSelectionActionModeCallback = lookupCallback()
        }
        content.addView(source, LayoutParams(-1, -2).apply { topMargin = ctx.dp(6) })

        dictBox = LinearLayout(ctx).apply { orientation = VERTICAL }
        content.addView(dictBox, LayoutParams(-1, -2))

        val scroll = object : ScrollView(ctx) {
            override fun onMeasure(w: Int, h: Int) {
                super.onMeasure(w, MeasureSpec.makeMeasureSpec(maxHeightPx, MeasureSpec.AT_MOST))
            }
        }
        scroll.addView(content)
        addView(scroll, LayoutParams(-1, -2))
    }

    fun showLoading(msg: String) {
        translation.setTextColor(p.muted)
        translation.text = msg
        note.visibility = GONE
    }

    fun showError(msg: String) {
        translation.setTextColor(p.error)
        translation.text = msg
    }

    fun start(text: String, detected: SourceLang? = null, ctxText: String? = null) {
        paraContext = ctxText
        lang = when {
            Prefs.sourceLang != SourceLang.AUTO -> Prefs.sourceLang
            detected != null && detected != SourceLang.AUTO -> detected
            else -> Translator.detect(text)
        }
        langChip.text = lang.label
        source.setText(text)
        translateNow(text)
    }

    private fun cycleLang() {
        lang = if (lang == SourceLang.JA) SourceLang.ZH else SourceLang.JA
        langChip.text = lang.label
        translateNow(source.text.toString())
    }

    private fun translateNow(text: String) {
        job?.cancel()
        dictBox.removeAllViews()
        if (text.isBlank()) { showError("Không nhận diện được chữ nào. Thử khoanh vùng rộng hơn."); return }
        showLoading("Đang dịch...")
        job = scope.launch {
            try {
                val r = Translator.translate(text, lang, paraContext)
                translation.setTextColor(p.fg)
                translation.text = r.text
                engineLabel.text = r.engine
                note.text = r.note ?: ""
                note.visibility = if (r.note != null) VISIBLE else GONE
            } catch (e: TranslateException) {
                showError("Lỗi: ${e.message}")
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                showError("Lỗi: ${e.message}")
            }
            val compact = text.trim()
            if (lang == SourceLang.ZH && compact.length <= 8 && Dictionary.hanCount(compact) == compact.length) {
                lookup(compact, fromSelection = false)
            }
        }
    }

    private fun copyTranslation() {
        val cm = context().getSystemService(ClipboardManager::class.java)
        cm.setPrimaryClip(ClipData.newPlainText("Bản dịch", translation.text))
        Toast.makeText(context(), "Đã chép bản dịch", Toast.LENGTH_SHORT).show()
    }

    private fun context(): Context = getContext()

    private fun lookupCallback() = object : ActionMode.Callback {
        override fun onCreateActionMode(mode: ActionMode, menu: Menu): Boolean {
            menu.add(0, 1001, 0, "Tra từ").setShowAsAction(MenuItem.SHOW_AS_ACTION_ALWAYS)
            return true
        }
        override fun onPrepareActionMode(mode: ActionMode, menu: Menu) = false
        override fun onActionItemClicked(mode: ActionMode, item: MenuItem): Boolean {
            if (item.itemId != 1001) return false
            val s = source.selectionStart.coerceAtLeast(0)
            val e = source.selectionEnd.coerceAtLeast(0)
            val word = source.text.substring(minOf(s, e), maxOf(s, e)).trim()
            if (word.isNotEmpty()) lookup(word, fromSelection = true)
            mode.finish()
            return true
        }
        override fun onDestroyActionMode(mode: ActionMode) {}
    }

    private fun lookup(word: String, fromSelection: Boolean) {
        lookupJob?.cancel()
        dictBox.removeAllViews()
        val ctx = context()
        val box = LinearLayout(ctx).apply {
            orientation = VERTICAL
            background = rounded(p.surface, ctx.dpf(12f))
            setPadding(ctx.dp(12), ctx.dp(10), ctx.dp(12), ctx.dp(10))
        }
        dictBox.addView(box, LayoutParams(-1, -2).apply { topMargin = ctx.dp(10) })
        val title = ctx.label(word, 20f, p.fg, bold = true)
        box.addView(title)
        val ctxMeaning = ctx.label(if (fromSelection) "Đang dịch theo ngữ cảnh..." else "", 15f, p.accent)
        if (fromSelection) box.addView(ctxMeaning)

        lookupJob = scope.launch {
            if (fromSelection) {
                try {
                    val r = Translator.translate(word, lang, source.text.toString())
                    ctxMeaning.text = "Theo ngữ cảnh: ${r.text}"
                } catch (e: Exception) {
                    if (e is kotlinx.coroutines.CancellationException) throw e
                    ctxMeaning.text = "Không dịch được: ${e.message}"
                }
            }
            if (lang != SourceLang.ZH && Dictionary.hasKana(word)) return@launch
            Dictionary.ready()
            val hv = Dictionary.hanViet(word)
            if (hv.isNotBlank()) box.addView(ctx.label("Hán Việt: $hv", 14f, p.fg))
            var entries = Dictionary.lookup(word)
            if (entries.isNotEmpty()) {
                addEntries(box, entries.take(4))
            } else if (Dictionary.hanCount(word) > 1) {
                for (w in Dictionary.segment(word).distinct().take(8)) {
                    entries = Dictionary.lookup(w)
                    if (entries.isEmpty()) continue
                    box.addView(ctx.label("$w  -  ${Dictionary.hanViet(w)}", 15f, p.fg, bold = true).apply {
                        setPadding(0, ctx.dp(8), 0, 0)
                    })
                    addEntries(box, entries.take(2))
                }
            }
            if (box.childCount <= 2 && !fromSelection && hv.isBlank()) dictBox.removeAllViews()
        }
    }

    private fun addEntries(box: LinearLayout, entries: List<Dictionary.Entry>) {
        val ctx = context()
        for (e in entries) {
            val head = if (e.trad != e.simp) "${e.pinyin}   (${e.trad})" else e.pinyin
            box.addView(ctx.label(head, 14f, p.accent).apply { setPadding(0, ctx.dp(4), 0, 0) })
            box.addView(ctx.label(e.defs, 13f, p.muted).apply { setTextIsSelectable(true) })
        }
    }
}
