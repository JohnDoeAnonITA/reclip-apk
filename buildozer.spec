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
source.include_patterns = ffmpeg_arm64

# (list) Source files to exclude
source.exclude_dirs = .git,__pycache__,venv,downloads,bin,.buildozer
source.exclude_patterns = *.apk,*.aab,*.pyc

# (str) Application versioning
version = 1.0.0

# (list) Application requirements
requirements = python3,kivy,flask,yt-dlp,certifi,libffi,openssl,android

# (str) Supported orientation
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (str) Application entry point
android.entrypoint = main.py

# (list) Permissions
android.permissions = INTERNET,READ_MEDIA_VIDEO,READ_MEDIA_AUDIO,WRITE_EXTERNAL_STORAGE

# (int) Android API to use
android.api = 34

# (int) Minimum API required
android.minapi = 24

# (str) Android NDK version
android.ndk = 25b

# (list) CPU architecture -- arm64 only (covers all modern phones, 2016+).
# Single ABI = half the build work and lower memory pressure.
android.archs = arm64-v8a

# (bool) Auto-accept the Android SDK licenses
android.accept_sdk_license = True

# (bool) Allow backups
android.allow_backup = True

# (str) python-for-android bootstrap: sdl2 = Kivy GUI (start/stop buttons)
p4a.bootstrap = sdl2
