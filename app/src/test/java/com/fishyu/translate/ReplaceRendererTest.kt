package com.fishyu.translate

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.Shader
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File
import kotlin.math.abs

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class ReplaceRendererTest {
    private class Scene(val bmp: Bitmap, val pieces: List<Piece>)

    private fun ink(c: Canvas, r: Rect, color: Int) {
        val p = Paint().apply { this.color = color }
        val step = r.height()
        var x = r.left
        while (x + step * 0.8f < r.right) {
            c.drawRect(x + step * 0.1f, r.top + step * 0.1f, x + step * 0.2f, r.bottom - step * 0.1f, p)
            c.drawRect(x + step * 0.1f, r.top + step * 0.45f, x + step * 0.85f, r.top + step * 0.55f, p)
            c.drawRect(x + step * 0.6f, r.top + step * 0.1f, x + step * 0.7f, r.bottom - step * 0.1f, p)
            x += step
        }
    }

    private fun scene(): Scene {
        val b = Bitmap.createBitmap(1080, 1400, Bitmap.Config.ARGB_8888)
        val c = Canvas(b)
        c.drawColor(Color.rgb(250, 246, 236))
        val pieces = ArrayList<Piece>()
        val lines1 = (0 until 4).map { i -> Rect(60, 80 + i * 70, if (i == 3) 600 else 1020, 80 + i * 70 + 52) }
        lines1.forEach { ink(c, it, Color.rgb(40, 34, 30)) }
        pieces += Piece(Rect(60, 80, 1020, 342), lines1, "细胞膜是包围细胞质的一层薄膜").apply {
            text = "Màng tế bào là một lớp màng mỏng bao quanh tế bào chất, giúp kiểm soát các chất đi vào và đi ra khỏi tế bào."
        }
        val grad = Paint().apply {
            shader = LinearGradient(0f, 450f, 1080f, 900f, Color.rgb(40, 90, 160), Color.rgb(200, 120, 60), Shader.TileMode.CLAMP)
        }
        c.drawRect(0f, 450f, 1080f, 900f, grad)
        val l2 = Rect(200, 640, 880, 700)
        ink(c, l2, Color.WHITE)
        pieces += Piece(Rect(l2), listOf(l2), "我们走吧").apply { text = "Chúng ta đi thôi!" }
        c.drawRect(0f, 1000f, 1080f, 1400f, Paint().apply { color = Color.rgb(30, 40, 60) })
        val lines3 = listOf(Rect(240, 1080, 840, 1130), Rect(340, 1150, 740, 1200))
        lines3.forEach { ink(c, it, Color.rgb(255, 230, 120)) }
        pieces += Piece(Rect(240, 1080, 840, 1200), lines3, "老师今天去哪里").apply { text = "Thầy ơi, hôm nay thầy đi đâu vậy?" }
        return Scene(b, pieces)
    }

    private fun composite(src: Bitmap, layer: Bitmap, alpha: Float): Bitmap {
        val out = src.copy(Bitmap.Config.ARGB_8888, true)
        Canvas(out).drawBitmap(layer, 0f, 0f, Paint().apply { this.alpha = (alpha * 255).toInt() })
        return out
    }

    private fun save(b: Bitmap, name: String) {
        val dir = File(System.getProperty("user.dir"), "build/replace-preview").apply { mkdirs() }
        File(dir, name).outputStream().use { b.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    private fun near(a: Int, b: Int, tol: Int) =
        abs(Color.red(a) - Color.red(b)) <= tol && abs(Color.green(a) - Color.green(b)) <= tol && abs(Color.blue(a) - Color.blue(b)) <= tol

    @Test
    fun erasesOriginalAndDrawsTranslation() {
        val s = scene()
        val out = ReplaceRenderer.render(s.bmp, s.pieces, 2.75f)
        assertTrue(out.painted.size == 3)
        val full = composite(s.bmp, out.bitmap, 1f)
        save(s.bmp, "source.png")
        save(full, "replaced.png")
        save(composite(s.bmp, out.bitmap, 0.79f), "replaced_80.png")

        val paper = Color.rgb(250, 246, 236)
        val r0 = out.painted[0]
        var paperPx = 0; var textPx = 0; var total = 0
        for (y in r0.top until r0.bottom step 3) for (x in r0.left until r0.right step 3) {
            val c = full.getPixel(x, y); total++
            if (near(c, paper, 12)) paperPx++
            if (near(c, Color.rgb(40, 34, 30), 40)) textPx++
        }
        assertTrue("phần lớn vùng phải là nền giấy", paperPx > total * 0.6)
        assertTrue("phải có chữ dịch màu giống chữ gốc", textPx > total * 0.03)

        val probeOld = s.bmp.getPixel(60 + (52 * 0.15).toInt(), 80 + 26)
        assertTrue(near(probeOld, Color.rgb(40, 34, 30), 5))

        val r1 = out.painted[1]
        val mid = full.getPixel(r1.left + 4, r1.centerY())
        val expected = s.bmp.getPixel(r1.left - 3, r1.centerY())
        assertTrue("nền gradient phải được nối liền", near(mid, expected, 30))

        val r2 = out.painted[2]
        var yellow = 0
        for (y in r2.top until r2.bottom step 2) for (x in r2.left until r2.right step 2) {
            if (near(full.getPixel(x, y), Color.rgb(255, 230, 120), 50)) yellow++
        }
        assertTrue("chữ dịch giữ màu vàng của chữ gốc", yellow > 20)
    }

    @Test
    fun longTranslationGrowsInsteadOfVanishing() {
        val b = Bitmap.createBitmap(600, 400, Bitmap.Config.ARGB_8888).apply { eraseColor(Color.WHITE) }
        val line = Rect(20, 20, 200, 60)
        ink(Canvas(b), line, Color.BLACK)
        val p = Piece(Rect(line), listOf(line), "好").apply {
            text = "Một câu dịch rất dài so với chữ gốc chỉ có vài ký tự nên phải xuống dòng nhiều lần"
        }
        val out = ReplaceRenderer.render(b, listOf(p), 2f)
        val r = out.painted.single()
        assertTrue(r.height() > line.height() + 20)
        save(composite(b, out.bitmap, 1f), "grow.png")
    }

    @Test
    fun narrowBoxWidensInsteadOfBreakingWords() {
        val b = Bitmap.createBitmap(600, 400, Bitmap.Config.ARGB_8888).apply { eraseColor(Color.WHITE) }
        val line = Rect(500, 100, 540, 140)
        ink(Canvas(b), line, Color.BLACK)
        val p = Piece(Rect(line), listOf(line), "目").apply { text = "Mục tiêu" }
        val out = ReplaceRenderer.render(b, listOf(p), 3f)
        val r = out.painted.single()
        assertTrue(r.width() > line.width() + 20)
        assertTrue(r.right <= 600)
        save(composite(b, out.bitmap, 1f), "narrow.png")
    }
}
