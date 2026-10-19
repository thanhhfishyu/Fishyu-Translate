package com.fishyu.translate

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BubblePlacementTest {
    private val size = 168
    private val margin = 12
    private val top = 96

    @Test
    fun landscapeRightEdgeMapsInsidePortrait() {
        val (right, frac) = BubblePlacement.fromScreen(2400 - size - margin, 900, 2400, 1080, size, margin, top)
        assertTrue(right)
        val p = BubblePlacement.toScreen(right, frac, 1080, 2400, size, margin, top)
        assertEquals(1080 - size - margin, p.x)
        assertTrue(p.y in top..(2400 - size - margin))
    }

    @Test
    fun extremeFractionsAreClamped() {
        for (f in listOf(-5f, 0f, 0.5f, 1f, 9f)) for (r in listOf(true, false)) {
            val p = BubblePlacement.toScreen(r, f, 720, 1280, size, margin, top)
            assertTrue(p.x >= 0 && p.x + size <= 720)
            assertTrue(p.y >= 0 && p.y + size <= 1280)
        }
    }

    @Test
    fun tinyScreenDoesNotGoNegative() {
        val p = BubblePlacement.toScreen(true, 1f, 100, 100, size, margin, top)
        assertTrue(p.x >= 0 && p.y >= 0)
    }
}
