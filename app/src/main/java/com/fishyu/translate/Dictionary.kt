package com.fishyu.translate

import android.content.Context
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import java.util.zip.GZIPInputStream

object Dictionary {
    class Entry(val trad: String, val simp: String, val pinyin: String, val defs: String)

    private var words: HashMap<String, MutableList<Entry>> = HashMap()
    private var hanviet: HashMap<Char, String> = HashMap()
    private var maxLen = 1
    private var loader: Deferred<Unit>? = null

    fun preload(ctx: Context) {
        if (loader == null) {
            val app = ctx.applicationContext
            loader = App.scope.async(Dispatchers.IO) {
                try { load(app) } catch (e: Throwable) { CrashLog.save(app, e, "Dictionary.load") }
            }
        }
    }

    suspend fun ready() {
        preload(App.instance)
        loader?.await()
    }

    private fun load(ctx: Context) {
        val map = HashMap<String, MutableList<Entry>>(260_000)
        var ml = 1
        GZIPInputStream(ctx.assets.open("cedict.dat")).bufferedReader().useLines { lines ->
            for (line in lines) {
                val p = line.split('\t')
                if (p.size < 4) continue
                val e = Entry(p[0], p[1], p[2], p[3])
                map.getOrPut(e.simp) { ArrayList(1) }.add(e)
                if (e.trad != e.simp) map.getOrPut(e.trad) { ArrayList(1) }.add(e)
                if (e.simp.length > ml) ml = e.simp.length
            }
        }
        val hv = HashMap<Char, String>(10_000)
        GZIPInputStream(ctx.assets.open("hanviet.dat")).bufferedReader().useLines { lines ->
            for (line in lines) {
                val i = line.indexOf('\t')
                if (i == 1) hv[line[0]] = line.substring(2)
            }
        }
        words = map
        hanviet = hv
        maxLen = ml.coerceAtMost(12)
    }

    fun lookup(word: String): List<Entry> = words[word.trim()].orEmpty()

    fun hanViet(text: String): String =
        text.mapNotNull { c ->
            if (isHan(c)) hanviet[c]?.substringBefore(',')?.trim() ?: c.toString() else null
        }.joinToString(" ")

    fun segment(text: String): List<String> {
        val out = ArrayList<String>()
        var i = 0
        while (i < text.length) {
            if (!isHan(text[i])) { i++; continue }
            var found = 1
            for (len in minOf(maxLen, text.length - i) downTo 2) {
                if (words.containsKey(text.substring(i, i + len))) { found = len; break }
            }
            out.add(text.substring(i, i + found))
            i += found
        }
        return out
    }

    fun isHan(c: Char): Boolean {
        val b = Character.UnicodeBlock.of(c)
        return b == Character.UnicodeBlock.CJK_UNIFIED_IDEOGRAPHS ||
            b == Character.UnicodeBlock.CJK_UNIFIED_IDEOGRAPHS_EXTENSION_A ||
            b == Character.UnicodeBlock.CJK_COMPATIBILITY_IDEOGRAPHS
    }

    fun hasKana(s: String): Boolean = s.any {
        val b = Character.UnicodeBlock.of(it)
        b == Character.UnicodeBlock.HIRAGANA || b == Character.UnicodeBlock.KATAKANA
    }

    fun hanCount(s: String): Int = s.count { isHan(it) }
}
