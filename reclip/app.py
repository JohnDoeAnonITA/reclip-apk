"""ReClip backend - standard library only (no Flask, no yt-dlp subprocess).

Two Android-specific changes vs upstream:
  * Flask/Werkzeug/Jinja removed -> `http.server` (the template is plain HTML).
  * yt-dlp is used as a **Python library** instead of a subprocess. On Android
    there is no `python` executable, so `sys.executable` is empty and
    `subprocess.run([sys.executable, '-m', 'yt_dlp'])` fails with
    "[Errno 13] Permission denied: ''".

Routes (identical to upstream ReClip):
  GET  /                     -> templates/index.html
  GET  /static/<file>        -> static assets
  POST /api/info             -> yt-dlp metadata
  POST /api/playlist         -> yt-dlp flat playlist
  POST /api/download         -> start a download job
  GET  /api/status/<job_id>  -> job status
  GET  /api/file/<job_id>    -> download the finished file
"""

import glob
import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.environ.get("RECLIP_DOWNLOAD_DIR", os.path.join(HERE, "downloads"))
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
TEMPLATES_DIR = os.path.join(HERE, "templates")
STATIC_DIR = os.path.join(HERE, "static")

# Path to a bundled static ffmpeg binary (Android has none on PATH).
FFMPEG_LOC = os.environ.get("RECLIP_FFMPEG")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
}

jobs = {}


def ensure_streams():
    """p4a/Kivy can leave sys.stdout / sys.stderr as a plain `str` instead of a
    writable stream. yt-dlp writes error messages to sys.stderr, which then
    fails with "'str' object has no attribute 'write'" and hides the real error.
    Replace anything that is not writable with a devnull stream.
    """
    import sys as _sys

    for name in ("stdout", "stderr"):
        stream = getattr(_sys, name, None)
        if stream is None or not hasattr(stream, "write"):
            try:
                setattr(_sys, name, open(os.devnull, "w"))
            except Exception:
                pass


ensure_streams()


def ytdlp_opts(**extra):
    """Base yt-dlp options; adds the bundled ffmpeg when available."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
    }
    if FFMPEG_LOC:
        opts["ffmpeg_location"] = FFMPEG_LOC
    opts.update(extra)
    return opts


def run_download(job_id, url, format_choice, format_id):
    import yt_dlp

    job = jobs[job_id]
    outtmpl = os.path.join(DOWNLOAD_DIR, "%s.%%(ext)s" % job_id)
    opts = ytdlp_opts(outtmpl=outtmpl)

    if format_choice == "audio":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}
        ]
    elif format_id:
        opts["format"] = "%s+bestaudio/best" % format_id
        opts["merge_output_format"] = "mp4"
    else:
        opts["format"] = "bestvideo+bestaudio/best"
        opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        files = glob.glob(os.path.join(DOWNLOAD_DIR, "%s.*" % job_id))
        if not files:
            job["status"] = "error"
            job["error"] = "Download completed but no file was found"
            return

        wanted = ".mp3" if format_choice == "audio" else ".mp4"
        target = [f for f in files if f.endswith(wanted)]
        chosen = target[0] if target else files[0]
        for f in files:
            if f != chosen:
                try:
                    os.remove(f)
                except OSError:
                    pass

        ext = os.path.splitext(chosen)[1]
        title = ((info or {}).get("title") or job.get("title") or "").strip()
        if title:
            safe = "".join(c for c in title if c not in r'\/:*?"<>|').strip()[:100].strip()
            job["filename"] = ("%s%s" % (safe, ext)) if safe else os.path.basename(chosen)
        else:
            job["filename"] = os.path.basename(chosen)

        job["file"] = chosen
        job["status"] = "done"
    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)


class ReClipHandler(BaseHTTPRequestHandler):
    server_version = "ReClip/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, code, body=b"", ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj))

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _serve_file(self, path, download_name=None):
        if not path or not os.path.isfile(path):
            return self._json({"error": "File not found"}, 404)
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            return self._json({"error": str(exc)}, 500)
        ctype = CONTENT_TYPES.get(os.path.splitext(path)[1].lower(),
                                  "application/octet-stream")
        extra = {}
        if download_name:
            extra["Content-Disposition"] = 'attachment; filename="%s"' % download_name
        self._send(200, data, ctype, extra)

    # -- routes -------------------------------------------------------------
    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            return self._serve_file(os.path.join(TEMPLATES_DIR, "index.html"))
        if path.startswith("/static/"):
            return self._serve_file(os.path.join(STATIC_DIR, os.path.basename(path)))
        if path.startswith("/api/status/"):
            job = jobs.get(path.rsplit("/", 1)[-1])
            if not job:
                return self._json({"error": "Job not found"}, 404)
            return self._json({
                "status": job["status"],
                "error": job.get("error"),
                "filename": job.get("filename"),
            })
        if path.startswith("/api/file/"):
            job = jobs.get(path.rsplit("/", 1)[-1])
            if not job or job.get("status") != "done":
                return self._json({"error": "File not ready"}, 404)
            return self._serve_file(job["file"], job.get("filename"))
        return self._json({"error": "Not found"}, 404)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        data = self._read_json()
        if path == "/api/info":
            return self._api_info(data)
        if path == "/api/playlist":
            return self._api_playlist(data)
        if path == "/api/download":
            return self._api_download(data)
        return self._json({"error": "Not found"}, 404)

    def _api_info(self, data):
        url = (data.get("url") or "").strip()
        if not url:
            return self._json({"error": "No URL provided"}, 400)
        try:
            import yt_dlp

            with yt_dlp.YoutubeDL(ytdlp_opts(skip_download=True)) as ydl:
                info = ydl.extract_info(url, download=False)

            best_by_height = {}
            for f in (info or {}).get("formats", []) or []:
                height = f.get("height")
                if height and f.get("vcodec", "none") != "none":
                    tbr = f.get("tbr") or 0
                    if height not in best_by_height or tbr > (best_by_height[height].get("tbr") or 0):
                        best_by_height[height] = f

            formats = [{"id": f["format_id"], "label": "%sp" % h, "height": h}
                       for h, f in best_by_height.items()]
            formats.sort(key=lambda item: item["height"], reverse=True)

            return self._json({
                "title": (info or {}).get("title", ""),
                "thumbnail": (info or {}).get("thumbnail", ""),
                "duration": (info or {}).get("duration"),
                "uploader": (info or {}).get("uploader", ""),
                "formats": formats,
            })
        except Exception as exc:
            return self._json({"error": str(exc)}, 400)

    def _api_playlist(self, data):
        url = (data.get("url") or "").strip()
        if not url:
            return self._json({"error": "No URL provided"}, 400)
        try:
            import yt_dlp

            with yt_dlp.YoutubeDL(ytdlp_opts(extract_flat=True)) as ydl:
                info = ydl.extract_info(url, download=False)

            urls = []
            for entry in (info or {}).get("entries", []) or []:
                if not entry:
                    continue
                value = entry.get("url") or entry.get("webpage_url") or entry.get("id")
                if value:
                    urls.append(value)
            return self._json({"urls": urls})
        except Exception as exc:
            return self._json({"error": str(exc)}, 400)

    def _api_download(self, data):
        url = (data.get("url") or "").strip()
        if not url:
            return self._json({"error": "No URL provided"}, 400)
        job_id = uuid.uuid4().hex[:10]
        jobs[job_id] = {
            "status": "downloading",
            "url": url,
            "title": data.get("title", ""),
        }
        thread = threading.Thread(
            target=run_download,
            args=(job_id, url, data.get("format", "video"), data.get("format_id")),
        )
        thread.daemon = True
        thread.start()
        return self._json({"job_id": job_id})


def make_server(host, port):
    return ThreadingHTTPServer((host, port), ReClipHandler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8899))
    host = os.environ.get("HOST", "127.0.0.1")
    make_server(host, port).serve_forever()
