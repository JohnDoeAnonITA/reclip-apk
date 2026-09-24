"""Minimal Kivy smoke test - isolates Kivy/SDL2 from the real app code.

Writes a log visible in /sdcard/Download/reclip_boot.log (MediaStore) and shows
"TEST OK" on screen if Kivy starts.
"""

import sys
import traceback

_LOG = "reclip_boot.log"


def _dl(text):
    try:
        from jnius import autoclass

        act = autoclass("org.kivy.android.PythonActivity").mActivity
        res = act.getContentResolver()
        MS = autoclass("android.provider.MediaStore")
        CV = autoclass("android.content.ContentValues")
        C = autoclass("android.provider.MediaStore$MediaColumns")
        B = autoclass("android.os.Build")
        vals = CV()
        vals.put(C.DISPLAY_NAME, _LOG)
        vals.put(C.MIME_TYPE, "text/plain")
        if B.VERSION.SDK_INT >= 29:
            vals.put(C.RELATIVE_PATH, "Download")
        uri = res.insert(MS.Downloads.EXTERNAL_CONTENT_URI, vals)
        if uri is None:
            return
        stream = res.openOutputStream(uri, "wt")
        stream.write(text.encode("utf-8"))
        stream.flush()
        stream.close()
    except Exception:
        try:
            with open("/sdcard/Download/" + _LOG, "w") as handle:
                handle.write(text)
        except Exception:
            pass


def log(msg):
    line = "[TEST] " + str(msg)
    try:
        print(line, file=sys.stdout, flush=True)
    except Exception:
        pass
    _dl(line + "\n")


log("boot")
try:
    from kivy.app import App
    from kivy.uix.label import Label

    log("kivy import ok")

    class TestApp(App):
        def build(self):
            log("build() reached")
            return Label(text="TEST OK")

    log("starting run()")
    TestApp().run()
    log("run() returned")
except Exception:
    log("FAILED:\n" + traceback.format_exc())
    raise
