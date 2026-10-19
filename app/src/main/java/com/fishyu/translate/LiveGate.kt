package com.fishyu.translate

class LiveGate {
    sealed class Decision {
        object Empty : Decision()
        object NotCjk : Decision()
        object Same : Decision()
        object Wait : Decision()
        class Reuse(val translation: String) : Decision()
        class Translate(val norm: String) : Decision()
    }

    private var pending = ""
    private var shown = ""
    private val done = LinkedHashMap<String, String>()

    fun offer(text: String): Decision {
        val norm = normalize(text)
        if (norm.length < 2) { pending = ""; return Decision.Empty }
        val cjk = norm.count { Dictionary.isHan(it) || Dictionary.hasKana(it.toString()) }
        if (cjk < 2 || cjk * 10 < norm.length * 3) { pending = ""; return Decision.NotCjk }
        if (similarity(norm, shown) >= 0.8) { pending = ""; return Decision.Same }
        if (similarity(norm, pending) < 0.9) { pending = norm; return Decision.Wait }
        pending = ""
        shown = norm
        done.entries.firstOrNull { similarity(it.key, norm) >= 0.85 }?.let { return Decision.Reuse(it.value) }
        return Decision.Translate(norm)
    }

    val hasPending: Boolean get() = pending.isNotEmpty()
    val hasShown: Boolean get() = shown.isNotEmpty()

    fun remember(norm: String, translation: String) {
        done[norm] = translation
        if (done.size > 40) done.remove(done.keys.first())
    }

    fun failed() { shown = "" }

    fun reset(clearDone: Boolean = false) {
        pending = ""; shown = ""
        if (clearDone) done.clear()
    }

    companion object {
        fun normalize(s: String): String = buildString { for (c in s) if (Character.isLetterOrDigit(c)) append(c) }

        fun similarity(a: String, b: String): Double {
            if (a == b) return 1.0
            if (a.isEmpty() || b.isEmpty()) return 0.0
            val n = a.length
            val m = b.length
            var prev = IntArray(m + 1) { it }
            var cur = IntArray(m + 1)
            for (i in 1..n) {
                cur[0] = i
                for (j in 1..m) {
                    val cost = if (a[i - 1] == b[j - 1]) 0 else 1
                    cur[j] = minOf(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
                }
                val t = prev; prev = cur; cur = t
            }
            return 1.0 - prev[m].toDouble() / maxOf(n, m)
        }
    }
}
