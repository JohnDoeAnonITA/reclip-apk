"""ReClip Android launcher - Kivy control GUI.

Control panel:
  * "Avvia server"           -> starts ReClip's Flask server in a background thread
  * "Ferma server"           -> shuts it down cleanly
  * "Apri interfaccia web"   -> opens the UI in an in-app WebView (native Android
                                WebView overlaid on the Kivy surface). Press the
                                device BACK button to close it and return to the
                                control panel.

The server is ReClip's own Flask app (bundled in ./reclip/). It is started with
Werkzeug's ``make_server`` so it can be stopped on demand.
"""

import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))

# Make the bundled reclip package importable (it lives in ./reclip/).
sys.path.insert(0, os.path.join(HERE, "reclip"))

HOST = "127.0.0.1"
PORT = 8899


# --------------------------------------------------------------------------
# Portable environment (Android)
# --------------------------------------------------------------------------
def _writable_dir():
    """Return a writable directory for downloaded media (Android sandbox)."""
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
        from jnius import autoclass  # Android only

        return str(autoclass("android.os.Build").SUPPORTED_ABIS[0])
    except Exception:
        import platform

        return platform.machine()


FFMPEG_BY_ABI = {
    "arm64-v8a": "ffmpeg_arm64",
    "armeabi-v7a": "ffmpeg_armhf",
    "armeabi": "ffmpeg_armhf",
}


def _setup_ffmpeg(abi):
    """Pick, chmod and register the bundled ffmpeg for this ABI."""
    names = []
    preferred = FFMPEG_BY_ABI.get(abi)
    if preferred:
        names.append(preferred)
    names += ["ffmpeg_arm64", "ffmpeg_armhf", "ffmpeg"]
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


# --------------------------------------------------------------------------
# Server control (start / stop)
# --------------------------------------------------------------------------
class ServerThread(threading.Thread):
    """Runs the Flask app in a background thread; can be shut down."""

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
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label


class Root(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="vertical", padding="24dp", spacing="16dp", **kwargs
        )
        self.server = None
        self._webview = None
        self._back_listener = None

        self.status = Label(text="Server fermo", size_hint_y=0.4, halign="center")
        self.add_widget(self.status)

        self.start_btn = Button(text="Avvia server", font_size="20sp")
        self.start_btn.bind(on_release=self.start_server)
        self.add_widget(self.start_btn)

        self.stop_btn = Button(text="Ferma server", font_size="20sp", disabled=True)
        self.stop_btn.bind(on_release=self.stop_server)
        self.add_widget(self.stop_btn)

        self.open_btn = Button(
            text="Apri interfaccia web", font_size="20sp", disabled=True
        )
        self.open_btn.bind(on_release=self.open_ui)
        self.add_widget(self.open_btn)

    # --- server actions ----------------------------------------------------
    def start_server(self, *_):
        if self.server is not None:
            return
        self.status.text = "Avvio in corso..."
        try:
            self.server = ServerThread()
            self.server.start()
        except Exception as exc:  # pragma: no cover - device errors
            self.status.text = f"Errore: {exc}"
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
            f"Server attivo\nhttp://{HOST}:{PORT}" if running else "Server fermo"
        )
        self.start_btn.disabled = running
        self.stop_btn.disabled = not running
        self.open_btn.disabled = not running

    # --- in-app web view ---------------------------------------------------
    def open_ui(self, *_):
        url = f"http://{HOST}:{PORT}/"
        try:
            from android.runnable import run_on_ui_thread
            from jnius import PythonJavaClass, autoclass, java_method
        except Exception:
            # Desktop fallback: external browser.
            import webbrowser

            webbrowser.open(url)
            return

        if self._webview is not None:
            return  # already open

        WebView = autoclass("android.webkit.WebView")
        WebViewClient = autoclass("android.webkit.WebViewClient")
        LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")
        KeyEvent = autoclass("android.view.KeyEvent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        outer = self

        class BackKeyListener(PythonJavaClass):
            """Closes the WebView when the device BACK button is pressed."""

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
            # MATCH_PARENT == -1
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
        self.title = "ReClip"
        abi = _primary_abi()
        ffmpeg = _setup_ffmpeg(abi)
        print(f"[reclip] abi={abi} ffmpeg={ffmpeg}", flush=True)
        return Root()


if __name__ == "__main__":
    ReClipApp().run()
