package news.weaware.weaware

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import android.content.Intent

class MainActivity : FlutterActivity() {
    private var sharedLinkSink: EventChannel.EventSink? = null
    private var pendingSharedLink: String? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "weaware/shared_links/methods")
            .setMethodCallHandler { call, result ->
                if (call.method == "initialUri") result.success(intent?.dataString)
                else result.notImplemented()
            }
        EventChannel(flutterEngine.dartExecutor.binaryMessenger, "weaware/shared_links/events")
            .setStreamHandler(object : EventChannel.StreamHandler {
                override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                    sharedLinkSink = events
                    pendingSharedLink?.let { events?.success(it); pendingSharedLink = null }
                }

                override fun onCancel(arguments: Any?) { sharedLinkSink = null }
            })
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        intent.dataString?.let { uri ->
            val sink = sharedLinkSink
            if (sink == null) pendingSharedLink = uri else sink.success(uri)
        }
    }
}
