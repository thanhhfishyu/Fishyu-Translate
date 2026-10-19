package com.fishyu.translate

import android.content.Intent
import android.view.View
import android.widget.EditText
import android.view.ViewGroup
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "w411dp-h891dp-port-xxhdpi")
class FlowTest {
    private fun <T : View> find(v: View, cls: Class<T>): List<T> {
        val out = ArrayList<T>()
        if (cls.isInstance(v)) out.add(cls.cast(v)!!)
        if (v is ViewGroup) for (i in 0 until v.childCount) out += find(v.getChildAt(i), cls)
        return out
    }

    @Test
    fun bubbleSurvivesProjectionLoss() {
        Prefs.init(RuntimeEnvironment.getApplication())
        val svc = Robolectric.buildService(BubbleService::class.java).create().get()
        svc.ensureBubbleVisible()
        org.robolectric.Shadows.shadowOf(android.os.Looper.getMainLooper()).idle()
        assertTrue((BubbleService::class.java.getDeclaredField("bubble").apply { isAccessible = true }.get(svc) as View).isAttachedToWindow)
        val m = BubbleService::class.java.getDeclaredMethod("onProjectionLost").apply { isAccessible = true }
        m.invoke(svc)
        val f = BubbleService::class.java.getDeclaredField("bubble").apply { isAccessible = true }
        val bubble = f.get(svc) as View?
        org.robolectric.Shadows.shadowOf(android.os.Looper.getMainLooper()).idle()
        assertNotNull(bubble)
        assertTrue(bubble!!.isAttachedToWindow)
        assertEquals(View.VISIBLE, bubble.visibility)
    }

    @Test
    fun processTextOpensTranslateWindow() {
        val text = "细胞膜是包围细胞质的一层薄膜。"
        val i = Intent(Intent.ACTION_PROCESS_TEXT).putExtra(Intent.EXTRA_PROCESS_TEXT, text).setType("text/plain")
        val a = Robolectric.buildActivity(TranslateActivity::class.java, i).setup().get()
        val edits = find(a.window.decorView, EditText::class.java)
        assertTrue(edits.any { it.text.toString() == text })
    }

    @Test
    fun shareTextOpensTranslateWindow() {
        val text = "今日はいい天気ですね"
        val i = Intent(Intent.ACTION_SEND).putExtra(Intent.EXTRA_TEXT, text).setType("text/plain")
        val a = Robolectric.buildActivity(TranslateActivity::class.java, i).setup().get()
        assertTrue(find(a.window.decorView, EditText::class.java).any { it.text.toString() == text })
    }

    @Test
    fun mainScreenBuilds() {
        val a = Robolectric.buildActivity(MainActivity::class.java).setup().resume().pause().get()
        assertNotNull(a)
    }
}
