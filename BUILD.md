# ReClip → APK (buildozer / python-for-android)

Single **multi-ABI ("fat") shareable APK** that runs the ReClip Flask backend
**on the phone** and shows the UI in a native WebView pointed at
`http://127.0.0.1:<port>/`.

## Architectures

| ABI | Devices | Bundled ffmpeg |
|---|---|---|
| `arm64-v8a` | all modern phones (2016+) | `ffmpeg_arm64` |
| `armeabi-v7a` | older 32-bit ARM devices | `ffmpeg_armhf` |
| `x86` / `x86_64` | **emulator only** — no real phones | not bundled (add only for emulator testing) |

One APK contains both ABIs; Android installs the right one automatically.
`main.py` detects the running ABI (`android.os.Build.SUPPORTED_ABIS`) and
selects the matching ffmpeg binary.

## Why the build must happen on x86_64

The Android NDK and python-for-android only provide **x86_64** host toolchains.
The APK is *cross-compiled*: the compiler runs on x86_64 and produces the ARM
code above. An arm64 host (PRoot/Termux) **cannot** run the NDK, so `buildozer`
fails there regardless of configuration.

→ Build on an x86_64 Linux machine, or just push to GitHub (CI below).

## Layout

```
main.py                 entrypoint: writable dir + per-ABI ffmpeg + Flask server
buildozer.spec          p4a bootstrap = webview, archs = arm64-v8a, armeabi-v7a
reclip/                 patched ReClip source (app.py made portable)
  app.py                DOWNLOAD_DIR + yt-dlp/ffmpeg configurable via env
.github/workflows/android.yml   CI build on an x86_64 runner
ffmpeg_arm64            (added by CI) static ffmpeg for arm64-v8a
ffmpeg_armhf            (added by CI) static ffmpeg for armeabi-v7a
```

## Build via GitHub Actions (recommended)

1. Push the contents of this directory to a repo (root).
2. The `Build ReClip APK` workflow runs on push / manually.
3. Download `bin/*.apk` from the run's **Artifacts**.
4. Share it — users must allow installation from unknown sources.

Debug-signed (fine for personal sharing). For a release build add a keystore
and run `buildozer android release`.

## Build locally (x86_64 Linux only)

```bash
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk \
  python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
  libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev

pip install --user buildozer cython

# bundle ffmpeg for both ABIs
curl -L -o /tmp/a.tar.xz https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz
curl -L -o /tmp/b.tar.xz https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarmhf-gpl.tar.xz
tar -xJf /tmp/a.tar.xz -C /tmp && tar -xJf /tmp/b.tar.xz -C /tmp
cp /tmp/ffmpeg-master-latest-linuxarm64-gpl/bin/ffmpeg ./ffmpeg_arm64
cp /tmp/ffmpeg-master-latest-linuxarmhf-gpl/bin/ffmpeg ./ffmpeg_armhf
chmod +x ./ffmpeg_arm64 ./ffmpeg_armhf

buildozer -v android debug      # first run downloads the SDK/NDK (~4 GB)
```

Or with Docker (x86_64):

```bash
docker run --rm -it -v "$PWD":/app -w /app kivy/buildozer \
  bash -c "curl -fL -o /tmp/a.tar.xz https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz && \
           curl -fL -o /tmp/b.tar.xz https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarmhf-gpl.tar.xz && \
           tar -xJf /tmp/a.tar.xz -C /tmp && tar -xJf /tmp/b.tar.xz -C /tmp && \
           cp /tmp/ffmpeg-master-latest-linuxarm64-gpl/bin/ffmpeg ./ffmpeg_arm64 && \
           cp /tmp/ffmpeg-master-latest-linuxarmhf-gpl/bin/ffmpeg ./ffmpeg_armhf && \
           chmod +x ffmpeg_arm64 ffmpeg_armhf && buildozer -v android debug"
```

## Known risk points (expect to iterate on the first build)

- **ffmpeg on Android**: yt-dlp shells out to an `ffmpeg` *executable*. We bundle
  statically-linked arm ffmpeg binaries and pass `--ffmpeg-location`. If the
  yt-dlp FFmpeg-Builds binary refuses to run on Android (glibc vs bionic), swap
  in an Android-native static build (Termux `ffmpeg` package, or `ffmpeg-kit`).
- **WebView port**: `main.py` listens on `--port` / `PORT` / `ANDROID_PORT`,
  defaulting to the p4a webview bootstrap default (5000). Blank page → check the
  port the bootstrap logs and match it.
- **Background vs in-app**: with the `webview` bootstrap the server runs inside
  the app process (stops when the app is closed). True background execution
  requires a foreground service — a separate, larger effort.
- **Storage**: downloads go to a writable app-private dir
  (`RECLIP_DOWNLOAD_DIR`) and are served back via `/api/file/<id>`.
