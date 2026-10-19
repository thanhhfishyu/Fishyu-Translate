package com.fishyu.translate

import android.content.res.Configuration
import android.view.View
import android.view.WindowManager
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowWindowManagerImpl

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "w411dp-h891dp-port-xxhdpi")
class BubbleServiceTest {

    private fun bubbleOf(svc: BubbleService): Pair<View, WindowManager.LayoutParams> {
        val f = BubbleService::class.java.getDeclaredField("bubble").apply { isAccessible = true }
        val l = BubbleService::class.java.getDeclaredField("bubbleLp").apply { isAccessible = true }
        return (f.get(svc) as View) to (l.get(svc) as WindowManager.LayoutParams)
    }

    private fun screen(svc: BubbleService): Pair<Int, Int> {
        val z = ScreenInfo.get(svc)
        return z.width to z.height
    }

    private fun assertOnScreen(svc: BubbleService, tag: String) {
        val (v, lp) = bubbleOf(svc)
        val (w, h) = screen(svc)
        val size = (56 * svc.resources.displayMetrics.density).toInt()
        println("$tag screen=${w}x$h bubble=(${lp.x},${lp.y}) visible=${v.visibility == View.VISIBLE}")
        assertTrue("$tag x=${lp.x} w=$w", lp.x >= 0 && lp.x + size <= w)
        assertTrue("$tag y=${lp.y} h=$h", lp.y >= 0 && lp.y + size <= h)
        assertTrue("$tag visible", v.visibility == View.VISIBLE)
    }

    @Test
    fun bubbleStaysOnScreenAcrossRotation() {
        val app = RuntimeEnvironment.getApplication()
        Prefs.init(app)
        Prefs.resetBubble()
        val ctl = Robolectric.buildService(BubbleService::class.java).create()
        val svc = ctl.get()
        svc.ensureBubbleVisible()
        assertOnScreen(svc, "portrait start")

        RuntimeEnvironment.setQualifiers("w891dp-h411dp-land")
        svc.onConfigurationChanged(Configuration(app.resources.configuration))
        assertOnScreen(svc, "landscape")

        Prefs.bubbleRight = true
        Prefs.bubbleYFrac = 1f
        svc.onConfigurationChanged(Configuration(app.resources.configuration))
        assertOnScreen(svc, "landscape right-bottom")

        RuntimeEnvironment.setQualifiers("w411dp-h891dp-port")
        svc.onConfigurationChanged(Configuration(app.resources.configuration))
        assertOnScreen(svc, "back to portrait")

        ctl.destroy()
        val ctl2 = Robolectric.buildService(BubbleService::class.java).create()
        ctl2.get().ensureBubbleVisible()
        assertOnScreen(ctl2.get(), "restart after landscape")
    }

    @Test
    fun oldAbsolutePrefsDoNotHideBubble() {
        val app = RuntimeEnvironment.getApplication()
        app.getSharedPreferences("settings", 0).edit().putInt("bx", 2300).putInt("by", 5000).apply()
        Prefs.init(app)
        val svc = Robolectric.buildService(BubbleService::class.java).create().get()
        svc.ensureBubbleVisible()
        assertOnScreen(svc, "legacy prefs")
    }
}
