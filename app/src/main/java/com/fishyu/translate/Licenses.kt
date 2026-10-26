package com.fishyu.translate

import android.content.Context
import android.graphics.Typeface
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.RelativeSizeSpan
import android.text.style.StyleSpan

object Licenses {
    const val LICENSE = "LICENSE"
    const val NOTICES = "THIRD_PARTY_NOTICES.md"

    fun read(ctx: Context, name: String): String =
        runCatching { ctx.assets.open("licenses/$name").bufferedReader().use { it.readText() } }.getOrDefault("")

    fun full(ctx: Context): CharSequence {
        val out = SpannableStringBuilder()
        heading(out, "Fishyu Translate", 1)
        out.append(read(ctx, LICENSE).trim()).append("\n\n")
        out.append(format(read(ctx, NOTICES)))
        return out
    }

    fun format(md: String): CharSequence {
        val out = SpannableStringBuilder()
        val lines = md.lines()
        for ((i, raw) in lines.withIndex()) {
            val line = raw.trimEnd()
            val next = lines.getOrNull(i + 1)?.trim().orEmpty()
            when {
                line.startsWith("|") && next.startsWith("|---") -> Unit
                line.startsWith("|---") -> Unit
                line.startsWith("|") -> {
                    val cells = line.trim().trim('|').split("|").map { clean(it.trim()) }.filter { it.isNotEmpty() }
                    if (cells.isNotEmpty()) {
                        out.append("• ").append(cells.first())
                        if (cells.size > 1) out.append(": ").append(cells.drop(1).joinToString(". "))
                        out.append("\n")
                    }
                }
                line.startsWith("#") -> {
                    val level = line.takeWhile { it == '#' }.length
                    if (out.isNotEmpty() && !out.endsWith("\n\n")) out.append("\n")
                    heading(out, clean(line.drop(level).trim()), level)
                }
                line.startsWith("- ") -> out.append("• ").append(clean(line.drop(2))).append("\n")
                line.isBlank() -> if (out.isNotEmpty() && !out.endsWith("\n\n")) out.append("\n")
                else -> out.append(clean(line)).append("\n")
            }
        }
        return out
    }

    private fun clean(s: String) = s.replace("`", "").replace("**", "")

    private fun heading(out: SpannableStringBuilder, text: String, level: Int) {
        val start = out.length
        out.append(text)
        out.setSpan(StyleSpan(Typeface.BOLD), start, out.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        out.setSpan(RelativeSizeSpan(if (level <= 1) 1.25f else 1.1f), start, out.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        out.append("\n")
    }
}
