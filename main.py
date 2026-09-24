"""ReClip Android launcher - Kivy control GUI.

Control panel:
  * "Avvia server"           -> starts ReClip's Flask server in a background thread
  * "Ferma server"           -> shuts it down cleanly
  * "Apri interfaccia web"   -> opens the UI in an in-app WebView (BACK closes it)

Diagnostics: every boot step is mirrored to
    /sdcard/Download/reclip_boot.log
via MediaStore (so it is visible from the phone's Files/Downloads app), and any
Python exception is shown on screen instead of silently closing the app.
"""

import os
import sys
import threading
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.join(HERE, "reclip"))

HOST = "127.0.0.1"
PORT = 8899

# Bumped every build so the log tells us which APK actually ran.
BUILD_ID = "2026-09-24-closebtn"

_LOG_NAME = "reclip_boot.log"
_LOG_LINES = []
_DL_URI = None


# --------------------------------------------------------------------------
# Logging: app-private file + copy into /sdcard/Download via MediaStore
# --------------------------------------------------------------------------
def _log_app_path():
    base = os.environ.get("ANDROID_PRIVATE") or HERE
    return os.path.join(base, _LOG_NAME)


def _mirror_to_downloads(text):
    global _DL_URI
    try:
        from jnius import autoclass

        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        resolver = activity.getContentResolver()
        MediaStore = autoclass("android.provider.MediaStore")
        CV = autoclass("android.content.ContentValues")
        Cols = autoclass("android.provider.MediaStore$MediaColumns")
        Build = autoclass("android.os.Build")

        if _DL_URI is None:
            values = CV()
            values.put(Cols.DISPLAY_NAME, _LOG_NAME)
            values.put(Cols.MIME_TYPE, "text/plain")
            if Build.VERSION.SDK_INT >= 29:
                values.put(Cols.RELATIVE_PATH, "Download")
            _DL_URI = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)

        if _DL_URI is None:
            return
        stream = resolver.openOutputStream(_DL_URI, "wt")
        if stream is None:
            return
        stream.write(text.encode("utf-8"))
        stream.flush()
        stream.close()
    except Exception:
        # last resort: direct write (only works with legacy storage)
        try:
            with open("/sdcard/Download/" + _LOG_NAME, "w") as handle:
                handle.write(text)
        except Exception:
            pass


def _log(msg):
    line = str(msg)
    _LOG_LINES.append(line)
    try:
        with open(_log_app_path(), "a") as handle:
            handle.write(line + "\n")
    except Exception:
        pass
    _mirror_to_downloads("\n".join(_LOG_LINES) + "\n")
    try:
        print("[reclip] " + line, file=sys.stdout, flush=True)
    except Exception:
        pass


_log("=== boot start (build %s) ===" % BUILD_ID)


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


def _android_native_lib(name):
    """Path of a file shipped under the APK's lib/<abi>/ (executable there)."""
    try:
        from jnius import autoclass

        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        libdir = activity.getApplicationInfo().nativeLibraryDir
        path = os.path.join(libdir, name)
        if os.path.exists(path):
            return path
    except Exception:
        pass
    return None


def _guess_filename(content_disposition, url):
    """Best-effort filename from a Content-Disposition header or the URL."""
    name = ""
    if content_disposition:
        for part in content_disposition.split(";"):
            part = part.strip()
            if part.lower().startswith("filename="):
                name = part.split("=", 1)[1].strip().strip('"')
                break
    if not name:
        name = url.rsplit("/", 1)[-1].split("?")[0] or "reclip_download"
    return name


def _probe_binary(path):
    """One-line description of whether `path` can actually be executed."""
    import subprocess

    parts = []
    try:
        st = os.stat(path)
        parts.append("mode=%o" % (st.st_mode & 0o777))
    except Exception as exc:
        parts.append("stat=ERR(%r)" % exc)
    parts.append("X_OK=%s" % os.access(path, os.X_OK))
    try:
        proc = subprocess.run(
            [path, "-version"], capture_output=True, text=True, timeout=20
        )
        first = ((proc.stdout or "") + (proc.stderr or "")).strip().split("\n")[0][:90]
        parts.append("rc=%s out=%r" % (proc.returncode, first))
    except Exception as exc:
        parts.append("EXEC FAILED: %r" % exc)
    return " ".join(parts)


def _setup_ffmpeg(abi):
    # Preferred: ffmpeg shipped as a native lib. On Android 10+ the app data
    # directory is noexec, so a binary stored there cannot be run at all.
    lib = _android_native_lib("libffmpeg.so")
    if lib:
        # Native libs can be installed without the exec bit.
        try:
            os.chmod(lib, 0o755)
        except OSError:
            pass
        _log("ffmpeg probe: " + _probe_binary(lib))
        os.environ.setdefault("RECLIP_FFMPEG", lib)
        return lib

    # Fallback (desktop / older Android): a plain file next to the app.
    for name in list(FFMPEG_CANDIDATES.get(abi, [])) + ["ffmpeg"]:
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
    """Runs ReClip's stdlib HTTP server in a background thread."""

    def __init__(self):
        super().__init__(daemon=True)
        from app import make_server

        self._srv = make_server(HOST, PORT)

    def run(self):
        try:
            self._srv.serve_forever()
        except Exception:
            _log("server serve_forever failed:\n" + traceback.format_exc())

    def stop(self):
        try:
            self._srv.shutdown()
            self._srv.server_close()
        except Exception:
            pass


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
    from kivy.metrics import dp
    from kivy.utils import get_color_from_hex

    _log("kivy imported ok")
except Exception:
    _log("KIVY IMPORT FAILED:\n" + traceback.format_exc())
    raise


class Root(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(
            orientation="vertical", padding=dp(24), spacing=dp(18), **kwargs
        )
        self.server = None
        self._webview = None
        self._back_listener = None
        self._dl_listener = None

        def big_button(text, bg):
            return Button(
                text=text,
                font_size=dp(25),
                bold=True,
                size_hint=(1, None),
                height=dp(78),
                background_normal="",
                background_down="",
                background_color=get_color_from_hex(bg),
                color=get_color_from_hex("#FFFFFF"),
            )

        # The WebView overlay leaves this strip visible, so this button can
        # always be tapped (the Android BACK key closes the whole activity
        # instead of reaching a View.OnKeyListener).
        self.close_btn = big_button("◀ Chiudi interfaccia web", "#455A64")
        self.close_btn.disabled = True
        self.close_btn.bind(on_release=self._close_webview)
        self.add_widget(self.close_btn)

        self.add_widget(Label(
            text="ReClip",
            font_size=dp(38),
            bold=True,
            size_hint_y=None,
            height=dp(70),
            color=get_color_from_hex("#5BC8FF"),
        ))

        self.status = Label(
            text="Server fermo",
            font_size=dp(19),
            halign="center",
            valign="middle",
            color=get_color_from_hex("#E0E0E0"),
        )
        self.status.bind(size=lambda lbl, size: setattr(lbl, "text_size", size))
        self.add_widget(self.status)

        self.start_btn = big_button("Avvia server", "#2E7D32")
        self.start_btn.bind(on_release=self.start_server)
        self.add_widget(self.start_btn)

        self.stop_btn = big_button("Ferma server", "#B71C1C")
        self.stop_btn.disabled = True
        self.stop_btn.bind(on_release=self.stop_server)
        self.add_widget(self.stop_btn)

        self.open_btn = big_button("Apri interfaccia web", "#1565C0")
        self.open_btn.disabled = True
        self.open_btn.bind(on_release=self.open_ui)
        self.add_widget(self.open_btn)

        # Native save path: works even if the WebView download handling fails.
        self.save_btn = big_button("Salva ultimo download", "#6A1B9A")
        self.save_btn.disabled = True
        self.save_btn.bind(on_release=self.save_last)
        self.add_widget(self.save_btn)

    def save_last(self, *_):
        import json as _json
        import urllib.request

        try:
            with urllib.request.urlopen(
                "http://%s:%s/api/last" % (HOST, PORT), timeout=10
            ) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
        except Exception:
            self.status.text = "Nessun download da salvare"
            return
        name = data.get("filename") or "reclip_download"
        url = "http://%s:%s/api/file/%s" % (HOST, PORT, data.get("id"))
        self._enqueue_download(url, name)

    def _enqueue_download(self, url, name):
        try:
            from jnius import autoclass, cast

            DownloadManager = autoclass("android.app.DownloadManager")
            DMRequest = autoclass("android.app.DownloadManager$Request")
            Context = autoclass("android.content.Context")
            Environment = autoclass("android.os.Environment")
            Uri = autoclass("android.net.Uri")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")

            activity = PythonActivity.mActivity
            manager = cast(
                "android.app.DownloadManager",
                activity.getSystemService(Context.DOWNLOAD_SERVICE),
            )
            request = DMRequest(Uri.parse(url))
            request.setTitle(name)
            request.setDescription("ReClip")
            request.setNotificationVisibility(
                DMRequest.VISIBILITY_VISIBLE_NOTIFY_COMPLETED
            )
            request.setDestinationInExternalPublicDir(
                Environment.DIRECTORY_DOWNLOADS, name
            )
            manager.enqueue(request)
            _log("native save enqueued: %s" % name)
            self.status.text = "Salvataggio avviato:\n%s" % name
        except Exception:
            tb = traceback.format_exc()
            _log("native save failed:\n" + tb)
            self.status.text = "Errore salvataggio:\n" + tb[-200:]

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
            from jnius import PythonJavaClass, autoclass, cast, java_method
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

        # --- downloads: an Android WebView IGNORES downloads unless a
        # DownloadListener is registered, which is why "Save" did nothing.
        DownloadManager = autoclass("android.app.DownloadManager")
        DMRequest = autoclass("android.app.DownloadManager$Request")
        Context = autoclass("android.content.Context")
        Environment = autoclass("android.os.Environment")
        Uri = autoclass("android.net.Uri")
        Intent = autoclass("android.content.Intent")
        activity_ref = activity

        class DownloadListener(PythonJavaClass):
            __javainterfaces__ = ["android/webkit/DownloadListener"]
            __javacontext__ = "app"

            @java_method(
                "(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;"
                "Ljava/lang/String;J)V"
            )
            def onDownloadStart(self, dl_url, user_agent, content_disposition,
                                mimetype, content_length):
                name = _guess_filename(content_disposition, dl_url)
                _log("download requested: %s -> %s" % (dl_url, name))
                try:
                    manager = cast(
                        "android.app.DownloadManager",
                        activity_ref.getSystemService(Context.DOWNLOAD_SERVICE),
                    )
                    request = DMRequest(Uri.parse(dl_url))
                    if mimetype:
                        request.setMimeType(mimetype)
                    request.setTitle(name)
                    request.setDescription("ReClip")
                    request.setNotificationVisibility(
                        DMRequest.VISIBILITY_VISIBLE_NOTIFY_COMPLETED
                    )
                    request.setDestinationInExternalPublicDir(
                        Environment.DIRECTORY_DOWNLOADS, name
                    )
                    manager.enqueue(request)
                    _log("download enqueued in DownloadManager")
                    return
                except Exception:
                    _log("DownloadManager failed:\n" + traceback.format_exc())
                try:
                    activity_ref.startActivity(
                        Intent(Intent.ACTION_VIEW, Uri.parse(dl_url))
                    )
                except Exception:
                    _log("browser fallback failed:\n" + traceback.format_exc())

        try:
            self._dl_listener = DownloadListener()
        except Exception:
            _log("download listener failed:\n" + traceback.format_exc())
            self._dl_listener = None

        @run_on_ui_thread
        def _show():
            wv = WebView(activity)
            settings = wv.getSettings()
            settings.setJavaScriptEnabled(True)
            settings.setDomStorageEnabled(True)
            wv.setWebViewClient(WebViewClient())
            if self._back_listener is not None:
                wv.setOnKeyListener(self._back_listener)
            if self._dl_listener is not None:
                wv.setDownloadListener(self._dl_listener)
            # Do NOT cover the whole screen: leave a strip at the top where the
            # Kivy "close" button stays visible and tappable.
            try:
                FrameLayout = autoclass("android.widget.FrameLayout")
                density = activity.getResources().getDisplayMetrics().density
                params = FrameLayout.LayoutParams(-1, -1)
                params.topMargin = int(116 * density)
            except Exception:
                _log("margin params failed:\n" + traceback.format_exc())
                params = LayoutParams(-1, -1)

            wv.loadUrl(url)
            activity.addContentView(wv, params)
            try:
                wv.setFocusableInTouchMode(True)
                wv.requestFocus()
            except Exception:
                pass
            self._webview = wv

        self.close_btn.disabled = False
        _show()

    def _close_webview(self, *_):
        wv = self._webview
        if wv is None:
            return
        self._webview = None
        try:
            self.close_btn.disabled = True
        except Exception:
            pass
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
