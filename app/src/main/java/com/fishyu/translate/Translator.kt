package com.fishyu.translate

import android.util.LruCache
import com.google.mlkit.common.model.DownloadConditions
import com.google.mlkit.nl.translate.TranslateLanguage
import com.google.mlkit.nl.translate.Translation
import com.google.mlkit.nl.translate.TranslatorOptions
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class TranslateResult(val text: String, val engine: String, val note: String? = null)

class TranslateException(msg: String) : Exception(msg)

object Translator {
    private val http = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()
    private val cache = LruCache<String, TranslateResult>(300)
    private val JSON = "application/json; charset=utf-8".toMediaType()

    fun detect(text: String): SourceLang {
        val pref = Prefs.sourceLang
        if (pref != SourceLang.AUTO) return pref
        return when {
            Dictionary.hasKana(text) -> SourceLang.JA
            Dictionary.hanCount(text) > 0 -> SourceLang.ZH
            else -> SourceLang.AUTO
        }
    }

    suspend fun translate(text: String, lang: SourceLang = detect(text), context: String? = null): TranslateResult {
        val clean = text.trim()
        if (clean.isEmpty()) throw TranslateException("Không có chữ để dịch")
        val key = "${Prefs.engine}|$lang|${context?.hashCode()}|${Prefs.glossaryText.hashCode()}|$clean"
        cache.get(key)?.let { return it }

        val useDeepl = Prefs.engine == Engine.DEEPL && Prefs.deeplKey.isNotEmpty()
        val result = if (useDeepl) {
            try {
                deepl(clean, lang, context)
            } catch (e: TranslateException) {
                if (!Prefs.fallbackOffline) throw e
                val r = offline(clean, lang)
                TranslateResult(r.text, r.engine, "DeepL lỗi: ${e.message} -> đã dịch offline")
            }
        } else {
            val r = offline(clean, lang)
            if (Prefs.engine == Engine.DEEPL) TranslateResult(r.text, r.engine, "Chưa nhập DeepL API key -> đang dịch offline")
            else r
        }
        cache.put(key, result)
        return result
    }

    private fun baseUrl(k: String) =
        if (k.endsWith(":fx")) "https://api-free.deepl.com" else "https://api.deepl.com"

    private fun escapeXml(s: String) =
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    private fun unescapeXml(s: String) =
        s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"")
            .replace("&apos;", "'").replace("&amp;", "&")

    private fun applyGlossaryXml(text: String): Pair<String, Boolean> {
        val gl = Prefs.glossary()
        var s = escapeXml(text)
        if (gl.isEmpty()) return s to false
        var used = false
        val holders = ArrayList<String>()
        for ((src, dst) in gl) {
            val esrc = escapeXml(src)
            if (s.contains(esrc)) {
                used = true
                val ph = "\u0000${holders.size}\u0000"
                holders.add("<x>${escapeXml(dst)}</x>")
                s = s.replace(esrc, ph)
            }
        }
        holders.forEachIndexed { i, h -> s = s.replace("\u0000$i\u0000", h) }
        return s to used
    }

    private suspend fun deepl(text: String, lang: SourceLang, context: String?): TranslateResult =
        withContext(Dispatchers.IO) {
            val k = Prefs.deeplKey
            val (marked, _) = applyGlossaryXml(text)
            val ctx = buildString {
                if (Prefs.domainHint.isNotBlank()) append(Prefs.domainHint.trim()).append('\n')
                if (!context.isNullOrBlank() && context.trim() != text) append(context.trim())
            }.trim()

            fun body(withModel: Boolean) = JSONObject().apply {
                put("text", JSONArray().put(marked))
                put("target_lang", "VI")
                lang.deepl?.let { put("source_lang", it) }
                if (ctx.isNotEmpty()) put("context", ctx)
                put("tag_handling", "xml")
                put("ignore_tags", JSONArray().put("x"))
                put("preserve_formatting", true)
                if (withModel) put("model_type", "prefer_quality_optimized")
            }.toString()

            fun call(withModel: Boolean): Pair<Int, String> {
                val req = Request.Builder()
                    .url(baseUrl(k) + "/v2/translate")
                    .header("Authorization", "DeepL-Auth-Key $k")
                    .post(body(withModel).toRequestBody(JSON))
                    .build()
                return try {
                    http.newCall(req).execute().use { it.code to (it.body?.string() ?: "") }
                } catch (e: Exception) {
                    throw TranslateException("không kết nối được (${e.javaClass.simpleName})")
                }
            }

            var (code, resp) = call(true)
            if (code == 400) {
                val r = call(false); code = r.first; resp = r.second
            }
            when (code) {
                200 -> {
                    val arr = JSONObject(resp).getJSONArray("translations")
                    val out = arr.getJSONObject(0).getString("text")
                        .replace("<x>", "").replace("</x>", "")
                    TranslateResult(unescapeXml(out), "DeepL")
                }
                403 -> throw TranslateException("API key không hợp lệ")
                456 -> throw TranslateException("đã hết quota tháng này")
                429 -> throw TranslateException("gửi quá nhanh, thử lại sau")
                else -> throw TranslateException("mã lỗi $code ${resp.take(120)}")
            }
        }

    suspend fun deeplUsage(key: String = Prefs.deeplKey): String = withContext(Dispatchers.IO) {
        if (key.isBlank()) return@withContext "Chưa có key"
        val req = Request.Builder()
            .url(baseUrl(key) + "/v2/usage")
            .header("Authorization", "DeepL-Auth-Key $key")
            .get().build()
        try {
            http.newCall(req).execute().use { r ->
                val s = r.body?.string() ?: ""
                if (r.code != 200) return@use if (r.code == 403) "Key không hợp lệ" else "Lỗi ${r.code}"
                val j = JSONObject(s)
                val used = j.optLong("character_count")
                val lim = j.optLong("character_limit")
                "Đã dùng %,d / %,d ký tự tháng này".format(used, lim)
            }
        } catch (e: Exception) {
            "Không kết nối được"
        }
    }

    private suspend fun offline(text: String, lang: SourceLang): TranslateResult {
        val src = when (lang) {
            SourceLang.JA -> TranslateLanguage.JAPANESE
            else -> TranslateLanguage.CHINESE
        }
        var t = text
        for ((a, b) in Prefs.glossary()) t = t.replace(a, b)
        val tr = Translation.getClient(
            TranslatorOptions.Builder()
                .setSourceLanguage(src)
                .setTargetLanguage(TranslateLanguage.VIETNAMESE)
                .build()
        )
        try {
            tr.downloadModelIfNeeded(DownloadConditions.Builder().build()).await()
            val out = tr.translate(t).await()
            return TranslateResult(out, "Google offline")
        } catch (e: Exception) {
            throw TranslateException("Dịch offline lỗi: ${e.message ?: "không tải được gói ngôn ngữ"}")
        } finally {
            tr.close()
        }
    }
}
