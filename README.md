<p align="center">
  <img src="docs/banner.png" alt="ReClip for Android" width="760">
</p>

<p align="center">
  <b>🇬🇧 English</b> &nbsp;·&nbsp; <a href="README.it.md">🇮🇹 Italiano</a>
</p>

# ReClip for Android

Download video and audio from 1000+ sites (YouTube, TikTok, Instagram,
Twitter/X, Reddit, Facebook, Vimeo, Twitch…) straight to your phone.

> ## ⚠️ Derivative work
>
> This project is a **derivative** of **[ReClip](https://github.com/averygan/reclip)**
> by [**averygan**](https://github.com/averygan), released under the **MIT**
> licence (Copyright (c) 2026).
>
> All credit for the original idea and application belongs to the **original
> author**. What was added here is only the *Android packaging*.
> The original `reclip/LICENSE` (MIT) is kept untouched.

---

## What it does

- **Web interface inside the app** — no browser, no server to set up
- **Real progress bar**: percentage, MB, speed and ETA
- **Saves directly to `Download/`**
- **Full quality video** (1080p/4K) and **MP3** audio
- **Two versions**: 🇬🇧 English and 🇮🇹 Italian

## The two versions

| Version | App name | Interface |
|---|---|---|
| 🇬🇧 English | **ReClip** | English |
| 🇮🇹 Italiano | **ReClip IT** | Italiano |

They have different package names, so you can **install both** side by side.

## Compatibility

| | |
|---|---|
| **Android** | **7.0 or newer** (API 24+). It does **not** install on Android 5/6. |
| **Feature phones (non-Android)** | ❌ not supported — no APK can run there |
| **CPU** | **arm64-v8a** (all modern phones) and **armeabi-v7a** (32-bit devices) |
| **Emulators (x86/x86_64)** | not included |
| **WebView** | needs a reasonably up-to-date *Android System WebView* / Chrome: on a very old WebView the interface cannot load |
| **RAM** | 2 GB or more recommended (Python + WebView): with 512 MB–1 GB it runs, but slowly |
| **Storage** | the APK is ~82 MB, plus the space for the files you download |

## Installation

1. Download the APK you want from the [**Releases**](../../releases) page
   (`reclip-en-release-signed.apk` or `reclip-it-release-signed.apk`).
2. Open it. Android will warn that installation from this source is not allowed.
3. Allow it, then install:
   - **Stock Android / Motorola:** *Settings → Apps → Special app access →
     Install unknown apps* → pick the app you are installing from (browser,
     Files, messaging app) → **Allow**
   - **Samsung:** *Settings → Apps → ⋮ (top right) → Special access →
     Install unknown apps* → pick the app → **Allow**
4. If Play Protect shows a warning, choose **Install anyway** (the app is not
   from the Play Store).
5. Open **ReClip**. The server starts by itself — just tap
   **Open web interface**.

> Already had an older **debug** build? Uninstall it first: it is signed with a
> different key, so it cannot be updated in place. Once you are on a release
> build, updates install over it without uninstalling.

## Building from source

See [**BUILD.md**](BUILD.md).

## Known limitations

- **Personal use**: downloading from third-party platforms may violate their
  terms of service. What you download is up to you.
- Saving goes through the app (an Android WebView cannot download on its own).
- Diagnostic logs are kept in the app's private storage and exported only on
  request through the **Export debug logs** button.

## Licence and credits

- **Original ReClip**: © 2026 [averygan](https://github.com/averygan) — [MIT](https://github.com/averygan/reclip/blob/main/LICENSE)
- **This derivative**: same **MIT** licence; the original text is preserved in
  `reclip/LICENSE`.
