package com.fishyu.translate

import kotlin.math.abs

class ScreenSig(val cols: Int, val rows: Int, val v: IntArray, val frame: Long = 0L) {
    companion object {
        fun changed(a: ScreenSig, b: ScreenSig, threshold: Int, mask: BooleanArray? = null): Float {
            if (a.cols != b.cols || a.rows != b.rows) return 1f
            var n = 0
            var total = 0
            for (i in a.v.indices) {
                if (mask != null && !mask[i]) continue
                total++
                if (abs(a.v[i] - b.v[i]) > threshold) n++
            }
            return if (total == 0) 0f else n.toFloat() / total
        }
    }

    fun zoneOf(rects: List<android.graphics.Rect>, cell: Int, grow: Int = 1): BooleanArray {
        val m = BooleanArray(cols * rows)
        for (r in rects) {
            val x0 = (r.left / cell - grow).coerceIn(0, cols - 1)
            val x1 = (r.right / cell + grow).coerceIn(0, cols - 1)
            val y0 = (r.top / cell - grow).coerceIn(0, rows - 1)
            val y1 = (r.bottom / cell + grow).coerceIn(0, rows - 1)
            for (y in y0..y1) for (x in x0..x1) m[y * cols + x] = true
        }
        return m
    }
}

class ReplaceGate(
    private val stableMs: Long = 450,
    private val touchQuietMs: Long = 450,
    private val calmLevel: Float = 0.12f,
) {
    enum class State { WAIT, BUSY, SHOWN, IDLE, PEEK }
    enum class Action { NONE, HIDE, PROCESS, SHOW_CACHED, PEEK }

    var peekOnTouch = false

    var state = State.WAIT
        private set
    var animated = false
        private set
    var hasRender = false
        private set
    val needsReference get() = state == State.SHOWN && ref == null

    private var prev: ScreenSig? = null
    private var stableSince = 0L
    private var calmSince = 0L
    private var quietUntil = 0L
    private var clean: ScreenSig? = null
    private var ref: ScreenSig? = null
    private var zone: BooleanArray? = null
    private var lastOcrKey: String? = null
    private var verifyAfter = 0L

    fun touch(now: Long): Action {
        quietUntil = maxOf(quietUntil, now + touchQuietMs)
        when (state) {
            State.SHOWN -> if (peekOnTouch) verifyAfter = now + touchQuietMs
            State.BUSY -> toWait(now)
            State.IDLE -> toWait(now)
            else -> Unit
        }
        return Action.NONE
    }

    fun frame(sig: ScreenSig, now: Long): Action {
        val p = prev
        prev = sig
        val d = if (p == null) 1f else ScreenSig.changed(p, sig, 8)
        if (d > 0.004f) stableSince = now
        if (d > calmLevel) calmSince = now
        return when (state) {
            State.WAIT -> onWait(sig, now)
            State.BUSY -> Action.NONE
            State.SHOWN -> onShown(sig, now)
            State.PEEK -> onPeek(sig, now)
            State.IDLE -> {
                val c = clean
                val limit = if (animated) 0.2f else 0.004f
                if (c == null || ScreenSig.changed(c, sig, 8) > limit) toWait(now)
                Action.NONE
            }
        }
    }

    private fun onWait(sig: ScreenSig, now: Long): Action {
        if (now < quietUntil) return Action.NONE
        val stable = now - stableSince >= stableMs
        val calm = now - calmSince >= stableMs
        if (!stable && !calm) return Action.NONE
        animated = !stable
        val c = clean
        if (hasRender && c != null && ScreenSig.changed(c, sig, 8) < 0.003f) {
            state = State.SHOWN
            ref = null
            return Action.SHOW_CACHED
        }
        state = State.BUSY
        return Action.PROCESS
    }

    private fun onShown(sig: ScreenSig, now: Long): Action {
        val r = ref ?: return Action.NONE
        val z = zone
        val moved = if (animated) {
            (z != null && ScreenSig.changed(r, sig, 6, z) > 0.05f) || ScreenSig.changed(r, sig, 8) > 0.3f
        } else {
            ScreenSig.changed(r, sig, 10) > 0.002f ||
                (!peekOnTouch && z != null && ScreenSig.changed(r, sig, 3, z) > 0.03f)
        }
        if (moved) {
            verifyAfter = 0L
            toWait(now)
            return Action.HIDE
        }
        val settled = now - (if (animated) calmSince else stableSince) >= stableMs
        if (verifyAfter != 0L && now >= verifyAfter && settled) {
            verifyAfter = 0L
            state = State.PEEK
            return Action.PEEK
        }
        return Action.NONE
    }

    private fun onPeek(sig: ScreenSig, now: Long): Action {
        val c = clean
        if (c != null && ScreenSig.changed(c, sig, 8) < 0.003f) {
            state = State.SHOWN
            ref = null
            return Action.SHOW_CACHED
        }
        toWait(now)
        return Action.NONE
    }

    fun ocrDone(textKey: String, now: Long): Boolean {
        if (!animated) {
            lastOcrKey = textKey
            return true
        }
        if (textKey == lastOcrKey) return true
        lastOcrKey = textKey
        state = State.WAIT
        stableSince = now
        calmSince = now - stableMs + 200
        return false
    }

    fun processed(sig: ScreenSig, zone: BooleanArray?) {
        clean = sig
        if (zone != null) {
            this.zone = zone
            hasRender = true
            state = State.SHOWN
            ref = null
        } else {
            hasRender = false
            state = State.IDLE
        }
    }

    fun reference(sig: ScreenSig) {
        if (state == State.SHOWN) ref = sig
    }

    fun abort(now: Long) {
        if (state == State.BUSY) toWait(now)
    }

    fun failed(now: Long, retryMs: Long = 4000) {
        quietUntil = now + retryMs
        toWait(now)
    }

    fun reset(now: Long) {
        clean = null
        hasRender = false
        lastOcrKey = null
        prev = null
        toWait(now)
    }

    private fun toWait(now: Long) {
        verifyAfter = 0L
        state = State.WAIT
        ref = null
        stableSince = now
        calmSince = now
    }
}
