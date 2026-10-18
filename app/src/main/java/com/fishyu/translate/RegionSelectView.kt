package com.fishyu.translate

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.DashPathEffect
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.RectF
import android.view.MotionEvent
import android.view.View
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

@SuppressLint("ViewConstructor")
class RegionSelectView(
    ctx: Context,
    private val shot: Bitmap,
    private val onRegion: (Rect) -> Unit,
    private val onTap: (Int, Int) -> Unit,
    private val onWholeScreen: () -> Unit,
    private val onCancel: () -> Unit,
) : View(ctx) {
    private val p = Palette(ctx)
    private val dim = Paint().apply { color = Color.argb(110, 0, 0, 0) }
    private val border = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = p.accent; style = Paint.Style.STROKE; strokeWidth = ctx.dpf(2.5f)
        pathEffect = DashPathEffect(floatArrayOf(ctx.dpf(8f), ctx.dpf(5f)), 0f)
    }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE; textSize = ctx.dpf(15f); textAlign = Paint.Align.CENTER
    }
    private val pill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.argb(200, 20, 20, 20) }
    private val btnPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = p.accent }

    private var sx = 0f; private var sy = 0f; private var ex = 0f; private var ey = 0f
    private var dragging = false
    private var busy = false
    private val cancelBtn = RectF()
    private val wholeBtn = RectF()
    private var status: String? = null

    fun setBusy(msg: String) { busy = true; status = msg; invalidate() }

    private val loc = IntArray(2)

    override fun onDraw(c: Canvas) {
        getLocationOnScreen(loc)
        c.drawColor(Color.BLACK)
        c.drawBitmap(shot, -loc[0].toFloat(), -loc[1].toFloat(), null)
        val sel = selection()
        if (sel != null) {
            c.save()
            c.clipOutRectCompat(sel)
            c.drawRect(0f, 0f, width.toFloat(), height.toFloat(), dim)
            c.restore()
            c.drawRect(sel, border)
        } else {
            c.drawRect(0f, 0f, width.toFloat(), height.toFloat(), dim)
        }

        val msg = status ?: "Kéo để khoanh vùng  -  chạm vào đoạn chữ để dịch đoạn đó"
        val tw = textPaint.measureText(msg) + context.dpf(32f)
        val top = context.dpf(56f)
        c.drawRoundRect(RectF(width / 2f - tw / 2, top, width / 2f + tw / 2, top + context.dpf(40f)),
            context.dpf(20f), context.dpf(20f), pill)
        c.drawText(msg, width / 2f, top + context.dpf(26f), textPaint)

        if (!busy) {
            val bw = context.dpf(132f); val bh = context.dpf(44f); val gap = context.dpf(14f)
            val by = height - context.dpf(110f)
            cancelBtn.set(width / 2f - bw - gap / 2, by, width / 2f - gap / 2, by + bh)
            wholeBtn.set(width / 2f + gap / 2, by, width / 2f + bw + gap / 2, by + bh)
            c.drawRoundRect(cancelBtn, bh / 2, bh / 2, pill)
            c.drawRoundRect(wholeBtn, bh / 2, bh / 2, btnPaint)
            c.drawText("Huỷ", cancelBtn.centerX(), cancelBtn.centerY() + context.dpf(5f), textPaint)
            c.drawText("Cả màn hình", wholeBtn.centerX(), wholeBtn.centerY() + context.dpf(5f), textPaint)
        }
    }

    private fun Canvas.clipOutRectCompat(r: RectF) {
        if (android.os.Build.VERSION.SDK_INT >= 26) clipOutRect(r)
    }

    private fun selection(): RectF? {
        if (!dragging && abs(ex - sx) < 1 && abs(ey - sy) < 1) return null
        return RectF(min(sx, ex), min(sy, ey), max(sx, ex), max(sy, ey))
    }

    @SuppressLint("ClickableViewAccessibility")
    override fun onTouchEvent(e: MotionEvent): Boolean {
        if (busy) return true
        when (e.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                sx = e.x; sy = e.y; ex = e.x; ey = e.y; dragging = false
            }
            MotionEvent.ACTION_MOVE -> {
                ex = e.x; ey = e.y
                if (abs(ex - sx) > context.dp(10) || abs(ey - sy) > context.dp(10)) dragging = true
                if (dragging) invalidate()
            }
            MotionEvent.ACTION_UP -> {
                if (!dragging) {
                    when {
                        cancelBtn.contains(e.x, e.y) -> onCancel()
                        wholeBtn.contains(e.x, e.y) -> onWholeScreen()
                        else -> onTap(e.x.toInt() + loc[0], e.y.toInt() + loc[1])
                    }
                } else {
                    val r = selection()!!
                    if (r.width() < context.dp(16) || r.height() < context.dp(12)) {
                        dragging = false; sx = ex; sy = ey; invalidate()
                    } else {
                        val rect = Rect(r.left.toInt() + loc[0], r.top.toInt() + loc[1],
                            r.right.toInt() + loc[0], r.bottom.toInt() + loc[1])
                        if (rect.intersect(0, 0, shot.width, shot.height) && rect.width() > 4 && rect.height() > 4) {
                            onRegion(rect)
                        } else {
                            dragging = false; sx = ex; sy = ey; invalidate()
                        }
                    }
                }
            }
        }
        return true
    }
}
