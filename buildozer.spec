[app]

# (str) Title of your application
title = ReClip

# (str) Package name
package.name = reclip

# (str) Package domain (needed for android/ios packaging)
package.domain = com.reclip

# (str) Source code where the main package is located
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,jpeg,svg,html,css,js,json,txt

# (list) Patterns of files to include (binary ffmpeg has no extension)
# ffmpeg is shipped as a native lib (see android.add_libs_*), not as an asset.

# (list) Source files to exclude
source.exclude_dirs = .git,__pycache__,venv,downloads,bin,.buildozer,p4a-recipes,libs,docs
source.exclude_patterns = *.apk,*.aab,*.pyc

# (str) Application versioning
version = 1.0.0

# (str) Application icon (PNG in the project root)
icon.filename = %(source.dir)s/icon.png

# (str) Release artifact: 'apk' (directly installable) or 'aab' (Play bundle).
# buildozer 1.5 defaults to 'aab'; we want a shareable/installable APK.
android.release_artifact = apk

# (list) Application requirements
requirements = python3,kivy,yt-dlp,certifi,libffi,openssl,android

# (str) Supported orientation
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (str) Android entry point = the ACTIVITY CLASS (NOT the python file!).
# Setting this to "main.py" makes the manifest declare a non-existent Java
# class -> ClassNotFoundException -> instant crash before Python starts.
# Leave it commented to use the default org.kivy.android.PythonActivity.
#android.entrypoint = org.kivy.android.PythonActivity

# (list) Permissions
android.permissions = INTERNET,READ_MEDIA_VIDEO,READ_MEDIA_AUDIO,WRITE_EXTERNAL_STORAGE

# (int) Android API to use
android.api = 34

# (int) Minimum API required
android.minapi = 24

# (str) Android NDK version
android.ndk = 25b

# (list) CPU architectures -- one "fat" APK for real devices.
#   arm64-v8a   : all modern phones            <- ffmpeg_arm64
#   armeabi-v7a : older 32-bit ARM devices     <- ffmpeg_armhf
# x86/x86_64 are emulator-only and have no bundled ffmpeg -> excluded to keep
# the build under ~40 minutes.
android.archs = arm64-v8a, armeabi-v7a

# ffmpeg/ffprobe as native libs: the app data dir is noexec on Android 10+,
# but files under the APK's lib/<abi>/ are executable.
android.add_libs_arm64_v8a = libs/arm64-v8a/*.so
android.add_libs_armeabi_v7a = libs/armeabi-v7a/*.so

# (bool) Auto-accept the Android SDK licenses
android.accept_sdk_license = True

# (bool) Allow backups
android.allow_backup = True

# (str) python-for-android bootstrap: sdl2 = Kivy GUI (start/stop buttons)
p4a.bootstrap = sdl2

# Pin a python-for-android release whose host Python is 3.11. The current
# default (v2026.x) builds host CPython 3.14.2, whose pip is broken inside
# p4a's internal venv -> "cannot import name 'BuildDependencyInstallError'".
p4a.fork = kivy
p4a.branch = v2024.01.21

# CI clones python-for-android here and patches its manifest template to add
# android:usesCleartextTraffic="true" (the in-app WebView loads plain HTTP on
# 127.0.0.1, which Android blocks for targetSdk >= 28).
p4a.source_dir = /tmp/p4a-patched

