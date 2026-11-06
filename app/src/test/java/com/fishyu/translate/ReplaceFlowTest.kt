package com.fishyu.translate

import android.Manifest
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowSettings

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ReplaceFlowTest {
    private fun texts(v: View): List<TextView> {
        val out = ArrayList<TextView>()
        if (v is TextView) out.add(v)
        if (v is ViewGroup) for (i in 0 until v.childCount) out += texts(v.getChildAt(i))
        return out
    }

    @Test
    fun replaceButtonAsksForCaptureThenStartsReplace() {
        val app = RuntimeEnvironment.getApplication()
        Prefs.init(app)
        ShadowSettings.setCanDrawOverlays(true)
        shadowOf(app).grantPermissions(Manifest.permission.POST_NOTIFICATIONS)
        val a = Robolectric.buildActivity(MainActivity::class.java).setup().get()
        val all = texts(a.window.decorView).map { it.text.toString() }
        assertTrue(all.contains("Thay chữ trên màn hình"))
        assertTrue(all.any { it.startsWith("Chưa bật") || it.startsWith("Đã bật") })
        texts(a.window.decorView).first { it.text.toString() == "Bật thay chữ" }.performClick()
        val next = shadowOf(a).nextStartedActivity
        assertEquals(ProjectionActivity::class.java.name, next.component?.className)
        assertEquals(BubbleService.THEN_REPLACE, next.getIntExtra(BubbleService.EXTRA_THEN, 0))
    }

    @Test
    fun passThroughAlphaStaysBelowAndroidLimit() {
        val alpha = ReplaceSession.passThroughAlpha(RuntimeEnvironment.getApplication())
        assertTrue(alpha <= 0.8f && alpha >= 0.5f)
    }
}
