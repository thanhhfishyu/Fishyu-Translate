package com.fishyu.translate

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

class App : Application() {
    override fun onCreate() {
        super.onCreate()
        instance = this
        CrashLog.install(this)
        Prefs.init(this)
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL, "Bong bóng dịch", NotificationManager.IMPORTANCE_LOW)
        )
    }

    companion object {
        const val CHANNEL = "bubble"
        lateinit var instance: App
            private set
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    }
}
