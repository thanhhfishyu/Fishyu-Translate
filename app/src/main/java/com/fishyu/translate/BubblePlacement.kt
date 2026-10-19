package com.fishyu.translate

object BubblePlacement {
    data class Pos(val x: Int, val y: Int)

    fun toScreen(rightSide: Boolean, yFrac: Float, screenW: Int, screenH: Int, size: Int, margin: Int, topInset: Int): Pos {
        val minY = topInset
        val maxY = (screenH - size - margin).coerceAtLeast(minY)
        val y = (minY + (maxY - minY) * yFrac.coerceIn(0f, 1f)).toInt()
        val x = if (rightSide) (screenW - size - margin).coerceAtLeast(0) else margin
        return Pos(x, y.coerceIn(minY, maxY))
    }

    fun fromScreen(x: Int, y: Int, screenW: Int, screenH: Int, size: Int, margin: Int, topInset: Int): Pair<Boolean, Float> {
        val right = x + size / 2 >= screenW / 2
        val minY = topInset
        val maxY = (screenH - size - margin).coerceAtLeast(minY)
        val frac = if (maxY == minY) 0f else ((y - minY).toFloat() / (maxY - minY)).coerceIn(0f, 1f)
        return right to frac
    }

    fun clamp(x: Int, y: Int, screenW: Int, screenH: Int, size: Int): Pos =
        Pos(x.coerceIn(0, (screenW - size).coerceAtLeast(0)), y.coerceIn(0, (screenH - size).coerceAtLeast(0)))
}
