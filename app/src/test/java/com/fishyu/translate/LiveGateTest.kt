package com.fishyu.translate

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class LiveGateTest {
    private fun run(gate: LiveGate, frames: List<String>): Int {
        var calls = 0
        for (f in frames) {
            val d = gate.offer(f)
            if (d is LiveGate.Decision.Translate) { calls++; gate.remember(d.norm, "vi:$f") }
        }
        return calls
    }

    @Test
    fun staticDialogTranslatedOnce() {
        val g = LiveGate()
        val line = "先生、今日はどこへ行きますか？"
        assertEquals(1, run(g, List(30) { line }))
    }

    @Test
    fun ocrNoiseFromAnimatedBackgroundDoesNotRetranslate() {
        val g = LiveGate()
        val frames = listOf(
            "先生、今日の任務は何ですか？", "先生、今日の任務は何ですか？",
            "先生、今日の任務は何ですか", "先生、今日の任務は向ですか？", "先生 今日の任務は何ですか？",
            "先生、今日の仕務は何ですか？", "・先生、今日の任務は何ですか？", "先生、今日の任務は何ですか？。",
        )
        assertEquals(1, run(g, frames))
    }

    @Test
    fun typewriterWaitsForFullLine() {
        val g = LiveGate()
        val full = "这个世界上没有不劳而获的东西"
        val frames = (2..full.length).map { full.substring(0, it) } + List(3) { full }
        var lastTranslated = ""
        for (f in frames) {
            val d = g.offer(f)
            if (d is LiveGate.Decision.Translate) { lastTranslated = f; g.remember(d.norm, f) }
        }
        assertEquals(full, lastTranslated)
    }

    @Test
    fun newLinesTranslatedAndRepeatsReused() {
        val g = LiveGate()
        val a = "我们走吧，时间不多了。"
        val b = "等一下，我还没准备好！"
        var calls = 0; var reuses = 0
        for (f in listOf(a, a, a, b, b, b, a, a, a)) {
            when (val d = g.offer(f)) {
                is LiveGate.Decision.Translate -> { calls++; g.remember(d.norm, "x") }
                is LiveGate.Decision.Reuse -> reuses++
                else -> {}
            }
        }
        assertEquals(2, calls)
        assertEquals(1, reuses)
    }

    @Test
    fun vietnameseHomeScreenIsIgnored() {
        val g = LiveGate()
        assertEquals(0, run(g, List(10) { "Cài đặt Tin nhắn Điện thoại Máy ảnh" }))
        assertEquals(0, run(g, List(10) { "12:45 Thứ Hai" }))
    }

    @Test
    fun retryAfterFailure() {
        val g = LiveGate()
        val a = "失败了再试一次吧"
        val d1 = g.offer(a); val d2 = g.offer(a)
        assertTrue(d1 is LiveGate.Decision.Wait && d2 is LiveGate.Decision.Translate)
        g.failed()
        g.offer(a)
        assertTrue(g.offer(a) is LiveGate.Decision.Translate)
    }
}
