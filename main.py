"""ReClip Android launcher - Kivy control GUI.

Control panel:
  * "Avvia server"           -> starts ReClip's Flask server in a background thread
  * "Ferma server"           -> shuts it down cleanly
  * "Apri interfaccia web"   -> opens the UI in an in-app WebView (BACK closes it)

Diagnostics: every step is logged to /sdcard/Android/data/<pkg>/files/reclip_boot.log
(visible over USB/MTP) and any Python exception is displayed on screen instead of
silently closing the app.
"""

import os
import sys
import threading
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.join(HERE, "reclip"))

HOST = "127.0.0.1"
PORT = 8899


# --------------------------------------------------------------------------
# Logging (to a user-reachable file + stdout/logcat)
# --------------------------------------------------------------------------
def _log_path():
    # Prefer the external files dir: readable over USB/MTP.
    try:
        from jnius import autoclass

        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        ext = activity.getExternalFilesDir(None)
        if ext is not None:
            return os.path.join(ext.getAbsolutePath(), "reclip_boot.log")
    except Exception:
        pass
    base = os.environ.get("ANDROID_PRIVATE") or HERE
    return os.path.join(base, "reclip_boot.log")


def _log(msg):
    try:
        with open(_log_path(), "a") as handle:
            handle.write(str(msg) + "\n")
    except Exception:
        pass
    try:
        print("[reclip] " + str(msg), file=sys.stdout, flush=True)
    except Exception:
        pass


_log("=== boot start ===")


# --------------------------------------------------------------------------
# Portable environment (Android)
# --------------------------------------------------------------------------
def _writable_dir():
    for base in (
        os.environ.get("ANDROID_PRIVATE"),
        os.environ.get("ANDROID_APP_PATH"),
        HERE,
    ):
        if not base:
            continue
        try:
            target = os.path.join(base, "reclip_downloads")
            os.makedirs(target, exist_ok=True)
            return target
        except OSError:
            continue
    return os.path.join(HERE, "downloads")


def _primary_abi():
    try:
        from jnius import autoclass

        return str(autoclass("android.os.Build").SUPPORTED_ABIS[0])
    except Exception:
        import platform

        return platform.machine()


FFMPEG_CANDIDATES = {
    "arm64-v8a": ["ffmpeg_arm64", "ffmpeg_armhf"],
    "armeabi-v7a": ["ffmpeg_armhf"],
    "armeabi": ["ffmpeg_armhf"],
    "x86_64": [],
    "x86": [],
}


def _setup_ffmpeg(abi):
    names = list(FFMPEG_CANDIDATES.get(abi, [])) + ["ffmpeg"]
    for name in names:
        path = os.path.join(HERE, name)
        if os.path.exists(path):
            try:
                os.chmod(path, 0o755)
            except OSError:
                pass
            os.environ.setdefault("RECLIP_FFMPEG", path)
            return path
    return None


os.environ.setdefault("RECLIP_DOWNLOAD_DIR", _writable_dir())
os.environ.setdefault("RECLIP_YTDLP_MODULE", "1")
_log("env ok, abi=" + _primary_abi())


# --------------------------------------------------------------------------
# Server control
# --------------------------------------------------------------------------
class ServerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        from werkzeug.serving import make_server

        from app import app as flask_app

        self._ctx = flask_app.app_context()
        self._srv = make_server(HOST, PORT, flask_app, threaded=True)

    def run(self):
        with self._ctx:
            self._srv.serve_forever()

    def stop(self):
        self._srv.shutdown()


# --------------------------------------------------------------------------
# Kivy UI
# --------------------------------------------------------------------------
try:
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView

    _log("kivy imported ok")
except Exception:
    _log("KIVY IMPORT FAILED:\n" + traceback.format_exc())
    raise


class Root(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=24, spacing=16, **kwargs)
        self.server = None
        self._webview = None
        self._back_listener = None

        self.status = Label(text="Server fermo", size_hint_y=0.4, halign="center")
        self.add_widget(self.status)

        self.start_btn = Button(text="Avvia server", font_size=20)
        self.start_btn.bind(on_release=self.start_server)
        self.add_widget(self.start_btn)

        self.stop_btn = Button(text="Ferma server", font_size=20, disabled=True)
        self.stop_btn.bind(on_release=self.stop_server)
        self.add_widget(self.stop_btn)

        self.open_btn = Button(text="Apri interfaccia web", font_size=20, disabled=True)
        self.open_btn.bind(on_release=self.open_ui)
        self.add_widget(self.open_btn)

    def start_server(self, *_):
        if self.server is not None:
            return
        self.status.text = "Avvio in corso..."
        try:
            self.server = ServerThread()
            self.server.start()
            _log("server started on %s:%s" % (HOST, PORT))
        except Exception:
            tb = traceback.format_exc()
            _log("SERVER START FAILED:\n" + tb)
            self.status.text = "Errore avvio:\n" + tb[-300:]
            self.server = None
            return
        Clock.schedule_once(lambda _dt: self._set_running(True), 0.6)

    def stop_server(self, *_):
        if self.server is None:
            return
        try:
            self.server.stop()
        except Exception:
            pass
        self.server = None
        self._set_running(False)

    def _set_running(self, running):
        self.status.text = (
            "Server attivo\nhttp://%s:%s" % (HOST, PORT) if running else "Server fermo"
        )
        self.start_btn.disabled = running
        self.stop_btn.disabled = not running
        self.open_btn.disabled = not running

    def open_ui(self, *_):
        url = "http://%s:%s/" % (HOST, PORT)
        try:
            from android.runnable import run_on_ui_thread
            from jnius import PythonJavaClass, autoclass, java_method
        except Exception:
            import webbrowser

            webbrowser.open(url)
            return

        if self._webview is not None:
            return

        WebView = autoclass("android.webkit.WebView")
        WebViewClient = autoclass("android.webkit.WebViewClient")
        LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")
        KeyEvent = autoclass("android.view.KeyEvent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        outer = self

        class BackKeyListener(PythonJavaClass):
            __javainterfaces__ = ["android/view/View$OnKeyListener"]
            __javacontext__ = "app"

            @java_method("(Landroid/view/View;ILandroid/view/KeyEvent;)Z")
            def onKey(self, view, key_code, event):
                if (
                    key_code == KeyEvent.KEYCODE_BACK
                    and event.getAction() == KeyEvent.ACTION_DOWN
                ):
                    outer._close_webview()
                    return True
                return False

        try:
            self._back_listener = BackKeyListener()
        except Exception:
            _log("back listener failed:\n" + traceback.format_exc())
            self._back_listener = None

        @run_on_ui_thread
        def _show():
            wv = WebView(activity)
            settings = wv.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            wv.setWebViewClient(WebViewClient())
            if self._back_listener is not None:
                wv.setOnKeyListener(self._back_listener)
            wv.loadUrl(url)
            activity.addContentView(wv, LayoutParams(-1, -1))
            self._webview = wv

        _show()

    def _close_webview(self, *_):
        wv = self._webview
        if wv is None:
            return
        self._webview = None
        try:
            from android.runnable import run_on_ui_thread
        except Exception:
            return

        @run_on_ui_thread
        def _hide():
            try:
                parent = wv.getParent()
                if parent is not None:
                    parent.removeView(wv)
                wv.destroy()
            except Exception:
                pass

        _hide()


class ReClipApp(App):
    def build(self):
        try:
            abi = _primary_abi()
            ffmpeg = _setup_ffmpeg(abi)
            _log("build(): abi=%s ffmpeg=%s" % (abi, ffmpeg))
            return Root()
        except Exception:
            tb = traceback.format_exc()
            _log("BUILD FAILED:\n" + tb)
            self.title = "ReClip - ERROR"
            scroll = ScrollView()
            scroll.add_widget(Label(text=tb, font_size=12))
            return scroll


if __name__ == "__main__":
    try:
        ReClipApp().run()
    except Exception:
        _log("RUN FAILED:\n" + traceback.format_exc())
        raise
