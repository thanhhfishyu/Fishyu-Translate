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
    private val offlineClients = HashMap<String, com.google.mlkit.nl.translate.Translator>()
    private val offlineReady = HashSet<String>()
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

    suspend fun translate(
        text: String,
        lang: SourceLang = detect(text),
        context: String? = null,
        engine: Engine = Prefs.engine,
    ): TranslateResult {
        val clean = text.trim()
        if (clean.isEmpty()) throw TranslateException("Không có chữ để dịch")
        val key = "$engine|$lang|${context?.hashCode()}|${Prefs.glossaryText.hashCode()}|$clean"
        cache.get(key)?.let { return it }

        val useDeepl = engine == Engine.DEEPL && Prefs.deeplKey.isNotEmpty()
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
            if (engine == Engine.DEEPL) TranslateResult(r.text, r.engine, "Chưa nhập DeepL API key -> đang dịch offline")
            else r
        }
        cache.put(key, result)
        return result
    }

    private const val FREE_HOST = "https://api-free.deepl.com"
    private const val PRO_HOST = "https://api.deepl.com"
    @Volatile private var knownHost: Pair<String, String>? = null

    private fun hosts(k: String): List<String> {
        knownHost?.let { (key, host) -> if (key == k) return listOf(host) }
        return if (k.endsWith(":fx")) listOf(FREE_HOST, PRO_HOST) else listOf(PRO_HOST, FREE_HOST)
    }

    private fun send(k: String, path: String, build: (Request.Builder) -> Request.Builder): Pair<Int, String> {
        var last = 0 to ""
        for (h in hosts(k)) {
            val req = build(Request.Builder().url(h + path).header("Authorization", "DeepL-Auth-Key $k")).build()
            last = http.newCall(req).execute().use { it.code to (it.body?.string() ?: "") }
            if (last.first != 403) {
                knownHost = k to h
                return last
            }
        }
        return last
    }

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
                return try {
                    send(k, "/v2/translate") { it.post(body(withModel).toRequestBody(JSON)) }
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
                456 -> throw TranslateException("đã hết số ký tự của gói")
                429 -> throw TranslateException("gửi quá nhanh, thử lại sau")
                else -> throw TranslateException("mã lỗi $code ${resp.take(120)}")
            }
        }

    suspend fun deeplUsage(key: String = Prefs.deeplKey): String = withContext(Dispatchers.IO) {
        if (key.isBlank()) return@withContext "Chưa có key"
        try {
            val (code, s) = send(key, "/v2/usage") { it.get() }
            if (code != 200) return@withContext if (code == 403) "Key không hợp lệ" else "Lỗi $code"
            val j = JSONObject(s)
            val used = j.optLong("character_count")
            val lim = j.optLong("character_limit")
            "Key hợp lệ. Đã dùng %,d / %,d ký tự".format(used, lim)
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
        val tr = offlineClients.getOrPut(src) {
            Translation.getClient(
                TranslatorOptions.Builder()
                    .setSourceLanguage(src)
                    .setTargetLanguage(TranslateLanguage.VIETNAMESE)
                    .build()
            )
        }
        try {
            if (src !in offlineReady) {
                tr.downloadModelIfNeeded(DownloadConditions.Builder().build()).await()
                offlineReady.add(src)
            }
            val out = tr.translate(t).await()
            return TranslateResult(out, "Google offline")
        } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e
            throw TranslateException("Dịch offline lỗi: ${e.message ?: "không tải được gói ngôn ngữ"}")
        }
    }
}
