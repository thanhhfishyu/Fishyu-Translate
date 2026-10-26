package com.fishyu.translate

import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowDialog

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class LicensesTest {
    private fun texts(v: View): List<TextView> {
        val out = ArrayList<TextView>()
        if (v is TextView) out.add(v)
        if (v is ViewGroup) for (i in 0 until v.childCount) out += texts(v.getChildAt(i))
        return out
    }

    @Test
    fun licenseFilesArePackaged() {
        val ctx = RuntimeEnvironment.getApplication()
        val mit = Licenses.read(ctx, Licenses.LICENSE)
        assertTrue(mit.contains("MIT License"))
        assertTrue(mit.contains("thanhhfishyu"))
        val notices = Licenses.read(ctx, Licenses.NOTICES)
        assertTrue(notices.contains("CC-CEDICT"))
        assertTrue(notices.contains("ML Kit"))
    }

    @Test
    fun markdownBecomesReadableText() {
        val md = "# Tiêu đề\n\n| Thành phần | Giấy phép |\n|---|---|\n| OkHttp | Apache-2.0 |\n\n- `a` link\n"
        val s = Licenses.format(md).toString()
        assertTrue(s.contains("• OkHttp: Apache-2.0"))
        assertTrue(s.contains("• a link"))
        assertFalse(s.contains("|"))
        assertFalse(s.contains("Thành phần"))
        assertFalse(s.contains("#"))
    }

    @Test
    fun mainScreenOpensLicenseDialog() {
        Prefs.init(RuntimeEnvironment.getApplication())
        val a = Robolectric.buildActivity(MainActivity::class.java).setup().get()
        val chip = texts(a.window.decorView).first { it.text.toString() == "Giấy phép mã nguồn mở" }
        chip.performClick()
        val dialog = ShadowDialog.getLatestDialog()
        assertTrue(dialog.isShowing)
        val body = texts(dialog.window!!.decorView).map { it.text.toString() }
        assertTrue(body.any { it.contains("MIT License") && it.contains("CC-CEDICT") })
    }
}
