package com.fishyu.translate

import android.content.Context
import android.content.SharedPreferences

enum class SourceLang(val label: String, val deepl: String?) {
    AUTO("Tự động", null),
    ZH("Tiếng Trung", "ZH"),
    JA("Tiếng Nhật", "JA");

    fun next(): SourceLang = entries[(ordinal + 1) % entries.size]
}

enum class Engine(val label: String) {
    DEEPL("DeepL (chuẩn ngữ cảnh)"),
    OFFLINE("Google offline (miễn phí, kém hơn)")
}

object Prefs {
    private lateinit var sp: SharedPreferences

    fun init(ctx: Context) {
        sp = ctx.getSharedPreferences("settings", Context.MODE_PRIVATE)
    }

    var deeplKey: String
        get() = sp.getString("deepl_key", "")!!.trim()
        set(v) = sp.edit().putString("deepl_key", v.trim()).apply()

    var sourceLang: SourceLang
        get() = runCatching { SourceLang.valueOf(sp.getString("src", "AUTO")!!) }.getOrDefault(SourceLang.AUTO)
        set(v) = sp.edit().putString("src", v.name).apply()

    var engine: Engine
        get() = runCatching { Engine.valueOf(sp.getString("engine", "DEEPL")!!) }.getOrDefault(Engine.DEEPL)
        set(v) = sp.edit().putString("engine", v.name).apply()

    var fallbackOffline: Boolean
        get() = sp.getBoolean("fallback", true)
        set(v) = sp.edit().putBoolean("fallback", v).apply()

    var domainHint: String
        get() = sp.getString("domain", "")!!
        set(v) = sp.edit().putString("domain", v).apply()

    var glossaryText: String
        get() = sp.getString("glossary", "")!!
        set(v) = sp.edit().putString("glossary", v).apply()

    var bubbleX: Int
        get() = sp.getInt("bx", -1)
        set(v) = sp.edit().putInt("bx", v).apply()

    var bubbleY: Int
        get() = sp.getInt("by", 300)
        set(v) = sp.edit().putInt("by", v).apply()

    fun glossary(): List<Pair<String, String>> =
        glossaryText.lineSequence()
            .map { it.trim() }
            .filter { it.isNotEmpty() && !it.startsWith("#") }
            .mapNotNull { line ->
                val i = line.indexOf('=')
                if (i <= 0) null
                else {
                    val a = line.substring(0, i).trim()
                    val b = line.substring(i + 1).trim()
                    if (a.isEmpty() || b.isEmpty()) null else a to b
                }
            }
            .sortedByDescending { it.first.length }
            .toList()
}
