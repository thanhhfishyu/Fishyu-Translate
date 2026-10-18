package com.fishyu.translate

import android.graphics.Bitmap
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.Text
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import com.google.mlkit.vision.text.japanese.JapaneseTextRecognizerOptions
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.tasks.await

class OcrResult(val text: String, val lang: SourceLang)

object OcrEngine {
    private val zh by lazy { TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build()) }
    private val ja by lazy { TextRecognition.getClient(JapaneseTextRecognizerOptions.Builder().build()) }

    suspend fun recognize(bmp: Bitmap, pref: SourceLang = Prefs.sourceLang): OcrResult {
        val (t, lang) = raw(upscaleIfSmall(bmp), pref)
        return OcrResult(assemble(t), lang)
    }

    suspend fun raw(bmp: Bitmap, pref: SourceLang = Prefs.sourceLang): Pair<Text, SourceLang> {
        val img = InputImage.fromBitmap(bmp, 0)
        return when (pref) {
            SourceLang.ZH -> zh.process(img).await() to SourceLang.ZH
            SourceLang.JA -> ja.process(img).await() to SourceLang.JA
            SourceLang.AUTO -> coroutineScope {
                val a = async { zh.process(img).await() }
                val b = async { ja.process(img).await() }
                val zt = a.await()
                val jt = b.await()
                val js = jt.text
                val kana = js.count { Dictionary.hasKana(it.toString()) }
                if (kana >= 2 && kana * 10 >= Dictionary.hanCount(js)) jt to SourceLang.JA
                else if (zt.text.isBlank()) jt to SourceLang.JA
                else zt to SourceLang.ZH
            }
        }
    }

    fun assembleBlock(b: Text.TextBlock): String {
        val sb = StringBuilder()
        for (line in b.lines) {
            val s = removeCjkSpaces(line.text.trim())
            if (s.isEmpty()) continue
            if (sb.isNotEmpty() && !(isCjk(sb.last()) || isCjk(s.first()))) sb.append(' ')
            sb.append(s)
        }
        return sb.toString()
    }

    private fun upscaleIfSmall(b: Bitmap): Bitmap {
        val minSide = minOf(b.width, b.height)
        if (minSide >= 160) return b
        val f = 160f / minSide
        return Bitmap.createScaledBitmap(b, (b.width * f).toInt(), (b.height * f).toInt(), true)
    }

    private fun isCjk(c: Char) = Dictionary.isHan(c) || Dictionary.hasKana(c.toString()) ||
        Character.UnicodeBlock.of(c) == Character.UnicodeBlock.CJK_SYMBOLS_AND_PUNCTUATION ||
        Character.UnicodeBlock.of(c) == Character.UnicodeBlock.HALFWIDTH_AND_FULLWIDTH_FORMS

    fun assemble(t: Text): String {
        val blocks = t.textBlocks.sortedWith(compareBy({ it.boundingBox?.top ?: 0 }, { it.boundingBox?.left ?: 0 }))
        return blocks.joinToString("\n") { assembleBlock(it) }.trim()
    }

    private fun removeCjkSpaces(s: String): String {
        val sb = StringBuilder()
        for (i in s.indices) {
            val c = s[i]
            if (c == ' ' && i > 0 && i < s.length - 1 && isCjk(s[i - 1]) && isCjk(s[i + 1])) continue
            sb.append(c)
        }
        return sb.toString()
    }
}
