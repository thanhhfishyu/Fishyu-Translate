package com.fishyu.translate

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ReplaceGateTest {
    private val cols = 10
    private val rows = 20

    private fun sig(fill: Int = 200, edit: (IntArray) -> Unit = {}) =
        ScreenSig(cols, rows, IntArray(cols * rows) { fill }.also(edit))

    private val page1 = sig { for (i in 20 until 120 step 3) it[i] = 60 }
    private val page2 = sig { for (i in 21 until 140 step 4) it[i] = 70 }
    private val zone = BooleanArray(cols * rows) { it in 10 until 150 }

    private fun ReplaceGate.feed(s: ScreenSig, from: Long, to: Long, step: Long = 160): List<ReplaceGate.Action> {
        val out = ArrayList<ReplaceGate.Action>()
        var t = from
        while (t <= to) { out += frame(s, t); t += step }
        return out
    }

    private fun ReplaceGate.untilPeek(s: ScreenSig, from: Long, to: Long): Boolean {
        var t = from
        while (t <= to) {
            if (frame(s, t) == ReplaceGate.Action.PEEK) return true
            t += 160
        }
        return false
    }

    @Test
    fun staticPageIsProcessedOnceItSettles() {
        val g = ReplaceGate()
        val a = g.feed(page1, 0, 300)
        assertFalse(ReplaceGate.Action.PROCESS in a)
        val b = g.feed(page1, 460, 800)
        assertEquals(1, b.count { it == ReplaceGate.Action.PROCESS })
        assertEquals(ReplaceGate.State.BUSY, g.state)
        assertTrue(g.ocrDone("a", 900))
        g.processed(page1, zone)
        assertEquals(ReplaceGate.State.SHOWN, g.state)
        assertTrue(g.needsReference)
    }

    @Test
    fun overlayStaysWhenTouchChangesNothing() {
        val g = ReplaceGate()
        g.feed(page1, 0, 700)
        g.ocrDone("a", 700)
        g.processed(page1, zone)
        val withOverlay = sig { for (i in 10 until 150) it[i] = 230 }
        g.reference(withOverlay)
        assertEquals(ReplaceGate.Action.NONE, g.touch(1000))
        val a = g.feed(withOverlay, 1000, 3000)
        assertTrue(a.all { it == ReplaceGate.Action.NONE })
        assertEquals(ReplaceGate.State.SHOWN, g.state)
    }

    @Test
    fun pageChangeHidesAndReprocesses() {
        val g = ReplaceGate()
        g.feed(page1, 0, 700)
        g.ocrDone("a", 700)
        g.processed(page1, zone)
        g.reference(page1)
        assertEquals(ReplaceGate.Action.HIDE, g.frame(page2, 1000))
        assertEquals(ReplaceGate.State.WAIT, g.state)
        val a = g.feed(page2, 1160, 1800)
        assertEquals(1, a.count { it == ReplaceGate.Action.PROCESS })
    }

    @Test
    fun opaqueOverlayPeeksAfterTouchAndReusesCachedRender() {
        val g = ReplaceGate().apply { peekOnTouch = true }
        g.feed(page1, 0, 700)
        g.ocrDone("a", 700)
        g.processed(page1, zone)
        val covered = sig { for (i in 10 until 150) it[i] = 250 }
        g.reference(covered)
        g.touch(1000)
        assertTrue(g.untilPeek(covered, 1000, 1700))
        assertEquals(ReplaceGate.State.PEEK, g.state)
        assertEquals(ReplaceGate.Action.SHOW_CACHED, g.frame(page1, 1900))
        assertEquals(ReplaceGate.State.SHOWN, g.state)
    }

    @Test
    fun opaqueOverlayPeekFindsNewPage() {
        val g = ReplaceGate().apply { peekOnTouch = true }
        g.feed(page1, 0, 700)
        g.ocrDone("a", 700)
        g.processed(page1, zone)
        val covered = sig { for (i in 10 until 150) it[i] = 250 }
        g.reference(covered)
        g.touch(1000)
        assertTrue(g.untilPeek(covered, 1000, 1700))
        g.frame(page2, 1900)
        assertEquals(ReplaceGate.State.WAIT, g.state)
        val a = g.feed(page2, 2060, 2700)
        assertEquals(1, a.count { it == ReplaceGate.Action.PROCESS })
    }

    @Test
    fun animatedScreenWaitsForSameTextTwice() {
        val g = ReplaceGate()
        var t = 0L
        var flip = false
        val acts = ArrayList<ReplaceGate.Action>()
        while (t < 1200) {
            flip = !flip
            val s = sig { for (i in 20 until 120 step 3) it[i] = 60; if (flip) for (i in 180 until 186) it[i] = 20 }
            acts += g.frame(s, t)
            t += 160
        }
        assertTrue(ReplaceGate.Action.PROCESS in acts)
        assertTrue(g.animated)
        assertFalse(g.ocrDone("first", t))
        assertEquals(ReplaceGate.State.WAIT, g.state)
        var again = false
        while (t < 2400 && !again) {
            flip = !flip
            val s = sig { for (i in 20 until 120 step 3) it[i] = 60; if (flip) for (i in 180 until 186) it[i] = 20 }
            again = g.frame(s, t) == ReplaceGate.Action.PROCESS
            t += 160
        }
        assertTrue(again)
        assertTrue(g.ocrDone("first", t))
    }

    @Test
    fun touchWhileBusyRestarts() {
        val g = ReplaceGate()
        g.feed(page1, 0, 700)
        assertEquals(ReplaceGate.State.BUSY, g.state)
        g.touch(800)
        assertEquals(ReplaceGate.State.WAIT, g.state)
        assertFalse(ReplaceGate.Action.PROCESS in g.feed(page1, 800, 1200))
        assertTrue(ReplaceGate.Action.PROCESS in g.feed(page1, 1360, 2000))
    }

    @Test
    fun emptyScreenIdlesUntilItChanges() {
        val g = ReplaceGate()
        val blank = sig()
        g.feed(blank, 0, 700)
        g.ocrDone("", 700)
        g.processed(blank, null)
        assertEquals(ReplaceGate.State.IDLE, g.state)
        assertTrue(g.feed(blank, 800, 2000).all { it == ReplaceGate.Action.NONE })
        g.frame(page1, 2100)
        assertEquals(ReplaceGate.State.WAIT, g.state)
    }
}
