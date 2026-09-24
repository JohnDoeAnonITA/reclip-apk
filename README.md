<p align="center">
  <img src="docs/banner.png" alt="ReClip for Android" width="760">
</p>

<p align="center">
  <b>🇬🇧 English</b> &nbsp;·&nbsp; <a href="README.it.md">🇮🇹 Italiano</a>
</p>

# ReClip for Android

Android APK build of **ReClip**, with a native GUI, an embedded web interface and
ffmpeg compiled for Android (video/audio merging and MP3 conversion working).

> ## ⚠️ Derivative work
>
> This project is a **derivative** of **[ReClip](https://github.com/averygan/reclip)**
> by [**averygan**](https://github.com/averygan), released under the **MIT**
> licence (Copyright (c) 2026).
>
> All credit for the original idea and application belongs to the **original
> author**. What was added here is only the *Android packaging*: Kivy GUI,
> in-app WebView, a Flask-free backend, native ffmpeg and the build pipeline.
> The original `reclip/LICENSE` (MIT) is kept untouched.

---

## What it does

ReClip downloads video/audio from 1000+ sites (YouTube, TikTok, Instagram,
Twitter/X, Reddit, Facebook, Vimeo, Twitch…). This version wraps it in a
standalone Android app:

- **Local HTTP server** started automatically on launch
- **Kivy control panel**: *Start/Stop server*, *Open/Close web interface*
- **In-app web UI** (native WebView) with a real **progress bar**
  (percentage, MB, speed, ETA)
- **Saves into `Download/`** (MediaStore; on Android ≤ 9 a direct file write)
- **ffmpeg 7.1 built with the NDK** → 1080p/4K merging and **MP3** (libmp3lame)
- **Export debug logs** button to retrieve the internal logs when needed
- Ships in **two variants**: 🇬🇧 English and 🇮🇹 Italian

## Two separate APKs

| Variant | Package | App name | Web UI | GUI |
|---|---|---|---|---|
| EN | `com.reclip.reclip` | ReClip | English | English |
| IT | `com.reclipit.reclipit` | ReClip IT | Italiano | Italiano |

Different package names → both apps **coexist** on the same device.

Requirements: **Android 7.0+** (min API 24), **arm64-v8a** or **armeabi-v7a**.
Installation from "unknown sources" (APK outside the Play Store).

## Build

Building happens on **GitHub Actions** (x86_64 runners). The workflow is
**manual**:

```
Actions → Build ReClip APK → Run workflow → variant: all | en | it
```

It produces **release APKs signed** with a dedicated keystore (read from
repository secrets) and publishes them as artifacts (+ release).

### Why CI and not a local build

The APK **cannot** be built on an arm64 host: the Android NDK and
python-for-android only exist for **x86_64**. The NDK is a *cross-compiler*: it
runs on x86_64 and emits ARM code for the phone.

## Layout

```
main.py                 entrypoint: Kivy GUI + WebView + file saving
buildozer.spec          python-for-android configuration (sdl2 bootstrap)
reclip/                 ReClip source (adapted for Android)
  app.py                backend rewritten with the stdlib only (no Flask)
  templates/index.html     web UI (English)
  templates/index_it.html  web UI (Italian)
docs/                   banner and logo for this README
.github/workflows/      build pipeline (EN/IT matrix)
libs/<abi>/libffmpeg.so native ffmpeg+ffprobe (built in CI, not in the repo)
```

## Technical differences from upstream

Behaviour and interface are ReClip's; the Android packaging required some
changes:

| Aspect | Upstream | Here |
|---|---|---|
| HTTP backend | Flask | **stdlib `http.server`** (Flask/Werkzeug cannot be installed reliably with p4a) |
| yt-dlp | CLI executable | **in-process Python library** (there is no `python` binary on Android) |
| ffmpeg | system binary | **built with the NDK**, shipped as a native library (the app data dir is `noexec`) |
| UI | browser | **in-app WebView** + Kivy GUI |
| Language | English | **EN and IT** (chosen at build time) |

Additionally the manifest gets `android:usesCleartextTraffic="true"`: the WebView
loads `http://127.0.0.1` and Android blocks cleartext HTTP for apps with
`targetSdk ≥ 28`.

## Known limitations

- **Personal use**: downloading from third-party platforms may violate their
  terms of service. What you download is up to you.
- Saving goes through the app (an Android WebView cannot download on its own).
- Diagnostic logs stay in the app's **private directory**; they are exported only
  on request via the *Export debug logs* button.

## Licence and credits

- **Original ReClip**: © 2026 [averygan](https://github.com/averygan) — [MIT](https://github.com/averygan/reclip/blob/main/LICENSE)
- **This derivative**: same **MIT** licence; the original text is preserved in
  `reclip/LICENSE`.
