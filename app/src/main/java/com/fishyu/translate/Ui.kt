package com.fishyu.translate

import android.content.Context
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.Drawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.LayerDrawable
import android.graphics.drawable.StateListDrawable
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.res.ResourcesCompat

class Palette(ctx: Context) {
    val dark = (ctx.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
        Configuration.UI_MODE_NIGHT_YES
    val page = c(dark, "#0F1824", "#EEF5FD")
    val bg = c(dark, "#182433", "#FFFFFF")
    val surface = c(dark, "#213044", "#EAF2FC")
    val fg = c(dark, "#EAF1FA", "#1E2A38")
    val muted = c(dark, "#9FB0C4", "#5E6B7C")
    val ink = c(dark, "#06090E", "#2B3442")
    val accent = c(dark, "#7FB2F0", "#3F7FD0")
    val accentSoft = c(dark, "#2F4A6E", "#A9C6EE")
    val onAccent = c(dark, "#0B1420", "#FFFFFF")
    val cheek = Color.parseColor("#F4B6B6")
    val line = c(dark, "#2E3F55", "#D3E2F4")
    val error = c(dark, "#FCA5A5", "#C0392B")

    private fun c(d: Boolean, night: String, day: String) = Color.parseColor(if (d) night else day)
}

object Fonts {
    private var bold: Typeface? = null
    private var medium: Typeface? = null
    fun bold(ctx: Context): Typeface =
        bold ?: (runCatching { ResourcesCompat.getFont(ctx, R.font.baloo_bold) }.getOrNull() ?: Typeface.DEFAULT_BOLD)
            .also { bold = it }
    fun medium(ctx: Context): Typeface =
        medium ?: (runCatching { ResourcesCompat.getFont(ctx, R.font.baloo_medium) }.getOrNull() ?: Typeface.DEFAULT)
            .also { medium = it }
}

fun Context.dp(v: Int): Int = (v * resources.displayMetrics.density).toInt()
fun Context.dpf(v: Float): Float = v * resources.displayMetrics.density

fun rounded(color: Int, radius: Float, stroke: Int = 0, strokeColor: Int = 0) = GradientDrawable().apply {
    setColor(color)
    cornerRadius = radius
    if (stroke > 0) setStroke(stroke, strokeColor)
}

fun Context.doodle(p: Palette, fill: Int, radius: Float = dpf(18f), shadow: Int = dp(4), stroke: Int = dp(2)): Drawable {
    val sh = rounded(p.ink, radius)
    val face = rounded(fill, radius, stroke, p.ink)
    return LayerDrawable(arrayOf(sh, face)).apply {
        setLayerInset(0, shadow, shadow, 0, 0)
        setLayerInset(1, 0, 0, shadow, shadow)
    }
}

private fun Context.pressable(p: Palette, fill: Int, radius: Float, shadow: Int): Drawable {
    val pressed = LayerDrawable(arrayOf(rounded(fill, radius, dp(2), p.ink))).apply {
        setLayerInset(0, shadow, shadow, 0, 0)
    }
    return StateListDrawable().apply {
        addState(intArrayOf(android.R.attr.state_pressed), pressed)
        addState(intArrayOf(), doodle(p, fill, radius, shadow))
    }
}

fun Context.label(text: String, sizeSp: Float, color: Int, bold: Boolean = false) = TextView(this).apply {
    this.text = text
    setTextSize(TypedValue.COMPLEX_UNIT_SP, sizeSp)
    setTextColor(color)
    if (bold) typeface = Fonts.bold(this@label)
}

fun Context.chip(text: String, p: Palette, filled: Boolean = false, onClick: (View) -> Unit) =
    TextView(this).apply {
        this.text = text
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
        typeface = Fonts.medium(this@chip)
        gravity = Gravity.CENTER
        val sh = dp(2)
        setPadding(dp(12), dp(5), dp(12) + sh, dp(6) + sh)
        setTextColor(if (filled) p.onAccent else p.fg)
        background = pressable(p, if (filled) p.accent else p.bg, dpf(14f), sh)
        isClickable = true
        setOnClickListener(onClick)
    }

fun Context.bigButton(text: String, p: Palette, filled: Boolean = true, onClick: (View) -> Unit) =
    TextView(this).apply {
        this.text = text
        setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f)
        typeface = Fonts.bold(this@bigButton)
        gravity = Gravity.CENTER
        val sh = dp(4)
        setPadding(dp(18), dp(10), dp(18) + sh, dp(10) + sh)
        setTextColor(if (filled) p.onAccent else p.fg)
        background = pressable(p, if (filled) p.accent else p.bg, dpf(16f), sh)
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
