"""ReClip backend - Flask replaced by the Python standard library.

Flask/Werkzeug are removed on purpose: p4a's `flask` recipe pins Flask 2.0.3
(2021) which is incompatible with the Werkzeug 3.x that pip installs, and modern
Flask has no setup.py so p4a's recipe cannot build it. The template is plain
HTML (no Jinja), and the API is 5 tiny endpoints, so `http.server` does the job
with zero third-party dependencies.

Same routes as upstream ReClip:
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
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.environ.get("RECLIP_DOWNLOAD_DIR", os.path.join(HERE, "downloads"))
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
TEMPLATES_DIR = os.path.join(HERE, "templates")
STATIC_DIR = os.path.join(HERE, "static")

# ---------------------------------------------------------------------------
# yt-dlp invocation (module inside the APK, CLI on desktop) + bundled ffmpeg
# ---------------------------------------------------------------------------
if os.environ.get("RECLIP_YTDLP_MODULE") == "1":
    YTDLP_CMD = [sys.executable, "-m", "yt_dlp"]
else:
    YTDLP_CMD = [os.environ.get("RECLIP_YTDLP", "yt-dlp")]

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


def ytdlp_base():
    base = list(YTDLP_CMD)
    if FFMPEG_LOC:
        base += ["--ffmpeg-location", FFMPEG_LOC]
    return base


def parse_ytdlp_json(stdout):
    """yt-dlp -j prints one JSON object per line; return the first valid one."""
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        return json.loads(line)
    raise ValueError("yt-dlp returned no data")


def run_download(job_id, url, format_choice, format_id):
    job = jobs[job_id]
    out_template = os.path.join(DOWNLOAD_DIR, "%s.%%(ext)s" % job_id)
    cmd = ytdlp_base() + ["--no-playlist", "-o", out_template]

    if format_choice == "audio":
        cmd += ["-x", "--audio-format", "mp3"]
    elif format_id:
        cmd += ["-f", "%s+bestaudio/best" % format_id, "--merge-output-format", "mp4"]
    else:
        cmd += ["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"]
    cmd.append(url)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            job["status"] = "error"
            job["error"] = result.stderr.strip().split("\n")[-1]
            return

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
        title = job.get("title", "").strip()
        if title:
            safe = "".join(c for c in title if c not in r'\/:*?"<>|').strip()[:100].strip()
            job["filename"] = ("%s%s" % (safe, ext)) if safe else os.path.basename(chosen)
        else:
            job["filename"] = os.path.basename(chosen)

        job["file"] = chosen
        job["status"] = "done"
    except subprocess.TimeoutExpired:
        job["status"] = "error"
        job["error"] = "Download timed out (5 min limit)"
    except Exception as exc:  # pragma: no cover
        job["status"] = "error"
        job["error"] = str(exc)


class ReClipHandler(BaseHTTPRequestHandler):
    server_version = "ReClip/1.0"
    protocol_version = "HTTP/1.1"

    # -- helpers ------------------------------------------------------------
    def log_message(self, *args):
        pass  # keep the device log clean

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
        cmd = ytdlp_base() + ["--no-playlist", "-j", url]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                return self._json({"error": result.stderr.strip().split("\n")[-1]}, 400)
            info = parse_ytdlp_json(result.stdout)

            best_by_height = {}
            for f in info.get("formats", []):
                height = f.get("height")
                if height and f.get("vcodec", "none") != "none":
                    tbr = f.get("tbr") or 0
                    if height not in best_by_height or tbr > (best_by_height[height].get("tbr") or 0):
                        best_by_height[height] = f

            formats = [{"id": f["format_id"], "label": "%sp" % h, "height": h}
                       for h, f in best_by_height.items()]
            formats.sort(key=lambda item: item["height"], reverse=True)

            return self._json({
                "title": info.get("title", ""),
                "thumbnail": info.get("thumbnail", ""),
                "duration": info.get("duration"),
                "uploader": info.get("uploader", ""),
                "formats": formats,
            })
        except subprocess.TimeoutExpired:
            return self._json({"error": "Timed out fetching video info"}, 400)
        except Exception as exc:
            return self._json({"error": str(exc)}, 400)

    def _api_playlist(self, data):
        url = (data.get("url") or "").strip()
        if not url:
            return self._json({"error": "No URL provided"}, 400)
        cmd = ytdlp_base() + ["--flat-playlist", "-J", url]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                return self._json({"error": result.stderr.strip().split("\n")[-1]}, 400)
            info = json.loads(result.stdout)
            urls = [e.get("url") for e in info.get("entries", []) if e.get("url")]
            return self._json({"urls": urls})
        except subprocess.TimeoutExpired:
            return self._json({"error": "Timed out fetching playlist info"}, 400)
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
    """Return a configured (not yet running) threading HTTP server."""
    return ThreadingHTTPServer((host, port), ReClipHandler)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8899))
    host = os.environ.get("HOST", "127.0.0.1")
    make_server(host, port).serve_forever()
