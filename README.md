# ReClip for Android

APK Android di **ReClip**, con GUI nativa, interfaccia web integrata e ffmpeg
compilato per Android (merge video/audio e conversione MP3 funzionanti).

> ## ⚠️ Opera derivata
>
> Questo progetto è un **derivato** di **[ReClip](https://github.com/averygan/reclip)**
> di [**averygan**](https://github.com/averygan), distribuito con licenza **MIT**
> (Copyright (c) 2026).
>
> Il merito dell'idea e dell'applicazione originale è **interamente dell'autore
> originale**. Qui è stato aggiunto solo il *packaging Android*: GUI Kivy,
> WebView in-app, backend senza Flask, ffmpeg nativo e pipeline di build.
> Il file `reclip/LICENSE` (MIT) è mantenuto intatto.

---

## Cosa fa

ReClip scarica video/audio da oltre 1000 siti (YouTube, TikTok, Instagram,
Twitter/X, Reddit, Facebook, Vimeo, Twitch…). Questa versione la incapsula in
un'app Android autonoma:

- **Server HTTP locale** avviato automaticamente all'apertura
- **Pannello di controllo** Kivy: *Start server* / *Stop server* / *Open web interface* / *Close web interface*
- **Interfaccia web in-app** (WebView nativa) con **barra di avanzamento** reale
  (percentuale, MB, velocità, ETA)
- **Salvataggio in `Download/`** con MediaStore (nomi con emoji inclusi)
- **ffmpeg 7.1 compilato col NDK** → merge 1080p/4K e **MP3** (libmp3lame)
- Pulsante **Export debug logs** per esportare i log interni quando servono
- Disponibile in **due varianti**: 🇬🇧 inglese e 🇮🇹 italiana

## Due APK separati

| Variante | Package | Nome app | UI web | GUI |
|---|---|---|---|---|
| EN | `com.reclip.reclip` | ReClip | English | English |
| IT | `com.reclipit.reclipit` | ReClip IT | Italiano | Italiano |

Package diversi → le due app **convivono** sullo stesso dispositivo.

Requisiti: **Android 7.0+** (min API 24), **arm64-v8a** o **armeabi-v7a**.
Installazione da "origini sconosciute" (APK fuori dal Play Store).

## Build

La compilazione avviene su **GitHub Actions** (runner x86_64). Il workflow è
**manuale**:

```
Actions → Build ReClip APK → Run workflow → variant: all | en | it
```

Produce APK **release firmati** con un keystore dedicato (letto dai repository
secrets) e li pubblica come artifact (+ release).

### Perché la CI e non in locale

L'APK **non può** essere compilato su un host arm64: Android NDK e
python-for-android esistono solo per **x86_64**. Il NDK è un *cross-compiler*:
gira su x86_64 e genera codice ARM per il telefono.

## Struttura

```
main.py                entrypoint: GUI Kivy + WebView + salvataggio file
buildozer.spec         configurazione python-for-android (bootstrap sdl2)
reclip/                sorgente ReClip (adattato per Android)
  app.py               backend riscritto con la sola stdlib (niente Flask)
  templates/index.html    UI web (inglese)
  templates/index_it.html UI web (italiano)
p4a-recipes/           (non usato) riservato a override di recipe
.github/workflows/     pipeline di build (matrix EN/IT)
libs/<abi>/libffmpeg.so   ffmpeg+ffprobe nativi (generati in CI, non nel repo)
```

## Differenze tecniche rispetto all'upstream

Il comportamento e l'interfaccia sono quelli di ReClip; il *packaging* Android
ha richiesto alcune modifiche:

| Aspetto | Upstream | Qui |
|---|---|---|
| Backend HTTP | Flask | **stdlib `http.server`** (Flask/Werkzeug non sono installabili in modo affidabile con p4a) |
| yt-dlp | eseguibile CLI | **libreria Python in-process** (su Android non esiste un binario `python`) |
| ffmpeg | binario di sistema | **compilato col NDK** e spedito come libreria nativa (la data dir dell'app è `noexec`) |
| UI | browser | **WebView in-app** + GUI Kivy |
| Lingua | inglese | **EN e IT** (scelta in build) |

## Limitazioni note

- **Uso personale**: il download da piattaforme terze può violare i loro termini
  di servizio. Valuta tu cosa scaricare.
- Il salvataggio dei file passa dall'app (una WebView Android non può scaricare
  da sola).
- I log diagnostici restano nella **cartella privata dell'app**; si esportano
  solo su richiesta col pulsante *Export debug logs*.

## Licenza e crediti

- **ReClip originale**: © 2026 [averygan](https://github.com/averygan) — [MIT](https://github.com/averygan/reclip/blob/main/LICENSE)
- **Questo derivato**: stessa licenza **MIT**; il testo originale è preservato in
  `reclip/LICENSE`.
