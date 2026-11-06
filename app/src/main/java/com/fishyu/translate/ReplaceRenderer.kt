package com.fishyu.translate

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Typeface
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

class Piece(val box: Rect, val lines: List<Rect>, val source: String) {
    var text: String = ""
}

object ReplaceRenderer {
    class Output(val bitmap: Bitmap, val painted: List<Rect>)

    private class Bg(val solid: Int?, val patch: IntArray?, val area: Rect, val mean: Int) {
        fun at(x: Int, y: Int): Int {
            if (solid != null) return solid
            val p = patch ?: return mean
            val ix = (x - area.left).coerceIn(0, area.width() - 1)
            val iy = (y - area.top).coerceIn(0, area.height() - 1)
            return p[iy * area.width() + ix]
        }
    }

    fun render(src: Bitmap, pieces: List<Piece>, density: Float): Output {
        val w = src.width
        val h = src.height
        val px = IntArray(w * h)
        src.getPixels(px, 0, w, 0, 0, w, h)
        val out = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(out)
        val painted = ArrayList<Rect>()
        for (p in pieces) {
            if (p.text.isBlank()) continue
            val r = runCatching { drawPiece(canvas, out, px, w, h, p, density) }.getOrNull()
            if (r != null) painted.add(r)
        }
        return Output(out, painted)
    }

    private fun median(v: List<Int>): Int {
        if (v.isEmpty()) return 0
        val s = v.sorted()
        return s[s.size / 2]
    }

    private fun dist(a: Int, b: Int): Int =
        (abs(Color.red(a) - Color.red(b)) + abs(Color.green(a) - Color.green(b)) + abs(Color.blue(a) - Color.blue(b))) / 3

    private fun luma(c: Int) = (Color.red(c) * 30 + Color.green(c) * 59 + Color.blue(c) * 11) / 100

    private fun medianColor(cs: List<Int>): Int =
        Color.rgb(median(cs.map { Color.red(it) }), median(cs.map { Color.green(it) }), median(cs.map { Color.blue(it) }))

    private fun ring(px: IntArray, w: Int, h: Int, a: Rect, band: Int): List<Int> {
        val out = ArrayList<Int>()
        val step = max(1, min(a.width(), a.height()) / 40)
        fun take(x: Int, y: Int) {
            if (x in 0 until w && y in 0 until h) out.add(px[y * w + x])
        }
        for (d in 1..band step max(1, band / 3)) {
            var x = a.left - band
            while (x <= a.right + band) { take(x, a.top - d); take(x, a.bottom - 1 + d); x += step }
            var y = a.top
            while (y < a.bottom) { take(a.left - d, y); take(a.right - 1 + d, y); y += step }
        }
        return out
    }

    private fun edge(px: IntArray, w: Int, h: Int, n: Int, band: Int, sample: (Int, Int) -> Pair<Int, Int>?): IntArray? {
        val acc = IntArray(n * 3)
        val cnt = IntArray(n)
        for (i in 0 until n) for (d in 1..band) {
            val (x, y) = sample(i, d) ?: continue
            if (x !in 0 until w || y !in 0 until h) continue
            val c = px[y * w + x]
            acc[i * 3] += Color.red(c); acc[i * 3 + 1] += Color.green(c); acc[i * 3 + 2] += Color.blue(c)
            cnt[i]++
        }
        if (cnt.count { it > 0 } < n / 3) return null
        val res = IntArray(n)
        var last = -1
        for (i in 0 until n) {
            if (cnt[i] > 0) {
                res[i] = Color.rgb(acc[i * 3] / cnt[i], acc[i * 3 + 1] / cnt[i], acc[i * 3 + 2] / cnt[i])
                if (last < 0) for (j in 0 until i) res[j] = res[i]
                last = i
            } else if (last >= 0) res[i] = res[last]
        }
        return blur(res, max(1, band))
    }

    private fun blur(a: IntArray, r: Int): IntArray {
        val out = IntArray(a.size)
        for (i in a.indices) {
            var rr = 0; var gg = 0; var bb = 0; var n = 0
            for (j in max(0, i - r)..min(a.size - 1, i + r)) {
                rr += Color.red(a[j]); gg += Color.green(a[j]); bb += Color.blue(a[j]); n++
            }
            out[i] = Color.rgb(rr / n, gg / n, bb / n)
        }
        return out
    }

    private fun background(px: IntArray, w: Int, h: Int, a0: Rect, band: Int): Bg {
        val a = Rect(a0)
        val samples = ring(px, w, h, a, band)
        val med = if (samples.isEmpty()) Color.WHITE else medianColor(samples)
        val uniform = samples.isEmpty() || samples.count { dist(it, med) <= 22 } >= samples.size * 0.88
        if (uniform) return Bg(med, null, a, med)
        val aw = a.width(); val ah = a.height()
        val top = edge(px, w, h, aw, band) { i, d -> a.left + i to a.top - d }
        val bottom = edge(px, w, h, aw, band) { i, d -> a.left + i to a.bottom - 1 + d }
        val left = edge(px, w, h, ah, band) { i, d -> a.left - d to a.top + i }
        val right = edge(px, w, h, ah, band) { i, d -> a.right - 1 + d to a.top + i }
        val t = top ?: bottom ?: return Bg(med, null, a, med)
        val b = bottom ?: t
        val l = left ?: right
        val r = right ?: l
        val patch = IntArray(aw * ah)
        for (y in 0 until ah) {
            val v = if (ah > 1) y.toFloat() / (ah - 1) else 0f
            for (x in 0 until aw) {
                val u = if (aw > 1) x.toFloat() / (aw - 1) else 0f
                patch[y * aw + x] = if (l == null || r == null) lerp(t[x], b[x], v)
                else coons(t, b, l, r, x, y, u, v)
            }
        }
        return Bg(null, patch, a, med)
    }

    private fun lerp(a: Int, b: Int, t: Float) = Color.rgb(
        (Color.red(a) + (Color.red(b) - Color.red(a)) * t).roundToInt(),
        (Color.green(a) + (Color.green(b) - Color.green(a)) * t).roundToInt(),
        (Color.blue(a) + (Color.blue(b) - Color.blue(a)) * t).roundToInt())

    private fun coons(t: IntArray, b: IntArray, l: IntArray, r: IntArray, x: Int, y: Int, u: Float, v: Float): Int {
        val p00 = t[0]; val p10 = t[t.size - 1]; val p01 = b[0]; val p11 = b[b.size - 1]
        fun ch(f: (Int) -> Int): Int {
            val c = (1 - v) * f(t[x]) + v * f(b[x]) + (1 - u) * f(l[y]) + u * f(r[y]) -
                ((1 - u) * (1 - v) * f(p00) + u * (1 - v) * f(p10) + (1 - u) * v * f(p01) + u * v * f(p11))
            return c.roundToInt().coerceIn(0, 255)
        }
        return Color.rgb(ch(Color::red), ch(Color::green), ch(Color::blue))
    }

    private fun contrast(bg: Int) = if (luma(bg) > 140) Color.rgb(20, 24, 30) else Color.rgb(250, 250, 250)

    private fun centered(lines: List<Rect>, lineH: Int, vertical: Boolean): Boolean {
        if (vertical || lines.size < 2) return false
        val lefts = lines.map { it.left }
        val centers = lines.map { it.centerX() }
        val spreadL = lefts.max() - lefts.min()
        val spreadC = centers.max() - centers.min()
        return spreadL > lineH * 0.8 && spreadC < spreadL * 0.5
    }

    private fun drawPiece(canvas: Canvas, out: Bitmap, px: IntArray, w: Int, h: Int, p: Piece, density: Float): Rect? {
        val lines = p.lines.filter { it.width() > 0 && it.height() > 0 }.ifEmpty { listOf(p.box) }
        val vertical = lines.count { it.height() > it.width() * 1.6f } * 2 > lines.size
        val lineH = median(lines.map { min(it.width(), it.height()) }).coerceAtLeast(6)
        val pad = max(2, (lineH * 0.14f).roundToInt())
        val band = max(3, (lineH * 0.2f).roundToInt())
        val area = Rect(p.box)
        lines.forEach { area.union(it) }
        area.inset(-pad, -pad)
        if (!area.intersect(0, 0, w, h)) return null

        val first = background(px, w, h, area, band)
        val ink = ArrayList<Pair<Int, Int>>()
        var seen = 0
        for (ln in lines) {
            val r = Rect(ln)
            if (!r.intersect(0, 0, w, h)) continue
            val step = max(1, min(r.width(), r.height()) / 18)
            var y = r.top
            while (y < r.bottom) {
                var x = r.left
                while (x < r.right) {
                    val c = px[y * w + x]
                    val d = dist(c, first.at(x, y))
                    seen++
                    if (d > 60) ink.add(c to d)
                    x += step
                }
                y += step
            }
        }
        val inkRatio = if (seen == 0) 0f else ink.size.toFloat() / seen
        var textColor = if (inkRatio < 0.02f) contrast(first.mean) else {
            val strong = ink.sortedByDescending { it.second }.take(max(1, ink.size / 2)).map { it.first }
            medianColor(strong)
        }
        if (abs(luma(textColor) - luma(first.mean)) < 60) textColor = contrast(first.mean)

        val tp = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
            typeface = if (inkRatio > 0.27f) Typeface.DEFAULT_BOLD else Typeface.create("sans-serif", Typeface.NORMAL)
            color = textColor
        }
        val align = if (centered(lines, lineH, vertical)) Layout.Alignment.ALIGN_CENTER else Layout.Alignment.ALIGN_NORMAL
        val minW = if (vertical) lineH * 3 else lineH
        if (area.width() - pad * 2 < minW) {
            val grow = (minW - (area.width() - pad * 2) + 1) / 2
            area.inset(-grow, 0)
            area.intersect(0, 0, w, h)
        }
        val innerW = max(4, area.width() - pad * 2)
        val innerH = max(4, area.height() - pad * 2)
        val text = p.text.trim()
        fun layout(fs: Float): StaticLayout {
            tp.textSize = fs
            return StaticLayout.Builder.obtain(text, 0, text.length, tp, innerW)
                .setAlignment(align)
                .setIncludePad(false)
                .setLineSpacing(0f, 1.0f)
                .build()
        }
        val maxFs = lineH * 0.84f
        val minFs = min(max(density * 9f, lineH * 0.4f), maxFs)
        var lo = minFs
        var hi = maxFs
        var best = layout(minFs)
        var fits = best.height <= innerH
        if (fits) {
            val top = layout(maxFs)
            if (top.height <= innerH) { best = top; lo = maxFs }
            else repeat(9) {
                val mid = (lo + hi) / 2
                val l = layout(mid)
                if (l.height <= innerH) { best = l; lo = mid } else hi = mid
            }
        }
        val fs = if (fits) lo else minFs
        best = layout(fs)
        if (!fits) {
            val need = best.height + pad * 2
            area.bottom = area.top + need
            if (area.bottom > h) area.offset(0, h - area.bottom)
            if (area.top < 0) area.top = 0
            fits = true
        }

        val bg = if (area == first.area) first else background(px, w, h, area, band)
        if (bg.solid != null) {
            val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = bg.solid }
            val rr = pad * 0.8f
            canvas.drawRoundRect(RectF(area), rr, rr, fill)
        } else {
            bg.patch?.let { out.setPixels(it, 0, area.width(), area.left, area.top, area.width(), area.height()) }
        }

        val dy = ((area.height() - pad * 2 - best.height) / 2).coerceAtLeast(0)
        canvas.save()
        canvas.translate((area.left + pad).toFloat(), (area.top + pad + dy).toFloat())
        if (bg.solid == null) {
            tp.style = Paint.Style.STROKE
            tp.strokeWidth = fs * 0.16f
            tp.strokeJoin = Paint.Join.ROUND
            tp.color = bg.mean
            best.draw(canvas)
            tp.style = Paint.Style.FILL
            tp.color = textColor
        }
        best.draw(canvas)
        canvas.restore()
        return Rect(area)
    }
}
