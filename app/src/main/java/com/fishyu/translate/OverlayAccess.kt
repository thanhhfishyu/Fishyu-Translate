package com.fishyu.translate

import android.accessibilityservice.AccessibilityService
import android.content.ComponentName
import android.content.Context
import android.provider.Settings
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent

class OverlayAccess : AccessibilityService() {
    companion object {
        @Volatile var instance: OverlayAccess? = null
            private set
        @Volatile var onChanged: (() -> Unit)? = null

        fun component(ctx: Context) = ComponentName(ctx, OverlayAccess::class.java)

        fun enabledInSettings(ctx: Context): Boolean {
            val list = Settings.Secure.getString(ctx.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES) ?: return false
            val me = component(ctx)
            return list.split(':').any { ComponentName.unflattenFromString(it) == me }
        }

        fun windowManager(): WindowManager? = instance?.let { s ->
            runCatching { s.getSystemService(WindowManager::class.java) }.getOrNull()
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        onChanged?.invoke()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onInterrupt() = Unit

    override fun onUnbind(intent: android.content.Intent?): Boolean {
        instance = null
        onChanged?.invoke()
        return super.onUnbind(intent)
    }

    override fun onDestroy() {
        instance = null
        onChanged?.invoke()
        super.onDestroy()
    }
}
