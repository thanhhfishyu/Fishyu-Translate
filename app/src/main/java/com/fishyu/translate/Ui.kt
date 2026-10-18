package com.fishyu.translate

import android.content.Context
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView

class Palette(ctx: Context) {
    val dark = (ctx.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
        Configuration.UI_MODE_NIGHT_YES
    val bg = if (dark) Color.parseColor("#1F1B18") else Color.parseColor("#FFFCF8")
    val surface = if (dark) Color.parseColor("#2A2521") else Color.parseColor("#F5EEE6")
    val fg = if (dark) Color.parseColor("#F3EDE7") else Color.parseColor("#1F1A17")
    val muted = if (dark) Color.parseColor("#A89F97") else Color.parseColor("#6B625B")
    val accent = if (dark) Color.parseColor("#FB923C") else Color.parseColor("#C2410C")
    val onAccent = Color.WHITE
    val line = if (dark) Color.parseColor("#3A332E") else Color.parseColor("#E7DDD3")
    val error = if (dark) Color.parseColor("#FCA5A5") else Color.parseColor("#B91C1C")
}

fun Context.dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()
fun Context.dpf(v: Float): Float = v * resources.displayMetrics.density

fun rounded(color: Int, radius: Float, stroke: Int = 0, strokeColor: Int = 0) = GradientDrawable().apply {
    setColor(color)
    cornerRadius = radius
    if (stroke > 0) setStroke(stroke, strokeColor)
}

fun Context.label(text: String, sizeSp: Float, color: Int, bold: Boolean = false) = TextView(this).apply {
    this.text = text
    setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp)
    setTextColor(color)
    if (bold) typeface = Typeface.DEFAULT_BOLD
}

fun Context.chip(text: String, p: Palette, filled: Boolean = false, onClick: (View) -> Unit) =
    TextView(this).apply {
        this.text = text
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        gravity = Gravity.CENTER
        setPadding(dp(12), dp(7), dp(12), dp(7))
        setTextColor(if (filled) p.onAccent else p.accent)
        background = if (filled) rounded(p.accent, dpf(16f))
        else rounded(Color.TRANSPARENT, dpf(16f), dp(1), p.accent)
        isClickable = true
        setOnClickListener(onClick)
    }

fun Context.hbox(vararg children: View, gap: Int = 8) = LinearLayout(this).apply {
    orientation = LinearLayout.HORIZONTAL
    gravity = Gravity.CENTER_VERTICAL
    children.forEachIndexed { i, v ->
        val lp = if (v.tag == SPACER) LinearLayout.LayoutParams(0, 1, 1f)
        else LinearLayout.LayoutParams(-2, -2).apply { if (i > 0) marginStart = dp(gap) }
        addView(v, lp)
    }
}

private const val SPACER = "spacer"
fun Context.spacer() = View(this).apply { tag = SPACER }
