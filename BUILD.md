# Compilare ReClip for Android dal sorgente

Guida tecnica per chi vuole ricompilare l'APK. Per l'installazione normale vedi
il [README](README.md).

---

## 1. Come si compila: GitHub Actions

La build gira su **GitHub Actions** ed è **manuale**:

```
Actions → Build ReClip APK → Run workflow → variant: all | en | it
```

| Variante | Package | Nome | UI web | GUI |
|---|---|---|---|---|
| `en` | `com.reclip.reclip` | ReClip | inglese | inglese |
| `it` | `com.reclipit.reclipit` | ReClip IT | italiano | italiano |

Produce **APK release firmati** e li pubblica come artifact e nella Release.

### Perché serve un host x86_64

Il **NDK Android e python-for-android esistono solo per x86_64**. Il NDK è un
*cross-compiler*: gira su x86_64 e genera codice ARM per il telefono. Su un host
arm64 (Termux, PRoot, Raspberry) **non è compilabile** — non è una questione di
configurazione, mancano proprio i binari del toolchain.

## 2. Secret richiesti nel repository

| Secret | Contenuto |
|---|---|
| `KEYSTORE_B64` | keystore di release, base64 (`base64 -w0 app.keystore`) |
| `KEYSTORE_PASS` | password del keystore |
| `KEYALIAS` | alias della chiave (es. `reclip`) |
| `KEYALIAS_PASS` | password della chiave |

Senza questi secret la pipeline produce comunque un APK, ma **non firmato** (non
installabile). Il keystore va conservato: senza, non si possono firmare
aggiornamenti dell'app già installata.

## 3. Cosa fa la pipeline (`.github/workflows/android.yml`)

1. **setup** — traduce l'input `variant` in una matrix di build
2. **checkout** + *Configure UI variant* — imposta `LANG` (lingua della GUI in
   `main.py`), `package.name/domain` e `title` nel `buildozer.spec`; per la
   variante IT copia `index_it.html` sopra `index.html`
3. **clone + patch di python-for-android** — clona il branch `v2024.01.21` e
   aggiunge `android:usesCleartextTraffic="true"` al template
   `AndroidManifest.tmpl.xml` (la WebView carica `http://127.0.0.1` e Android
   blocca il testo in chiaro con `targetSdk ≥ 28`)
4. **ffmpeg**: cache (`actions/cache`) dei binari già compilati; se manca, li
   compila col NDK (`arm64-v8a` + `armeabi-v7a`, con `libmp3lame`)
5. **build APK** — `buildozer -v android release`
6. **firma** — `zipalign` + `apksigner sign` con il keystore dai secret
   (buildozer 1.5 non ha opzioni keystore)
7. **upload** — artifact `reclip-apk-<variante>`

## 4. Struttura del progetto

```
main.py                 entrypoint: GUI Kivy + WebView + salvataggio file
buildozer.spec          configurazione python-for-android (bootstrap sdl2)
reclip/                 sorgente ReClip adattato
  app.py                backend con la sola stdlib (niente Flask)
  templates/index.html     UI web inglese
  templates/index_it.html  UI web italiana
docs/                   banner e logo del README
.github/workflows/      pipeline di build
libs/<abi>/libffmpeg.so ffmpeg+ffprobe nativi (generati in CI, non nel repo)
icon.png                icona dell'app (512×512)
```

Toolchain: **ubuntu-22.04**, Python 3.11, buildozer **1.5.0**, cython 0.29.36,
python-for-android **v2024.01.21**, JDK 17, Android API 34, minAPI 24.

## 5. Differenze tecniche rispetto all'upstream

| Aspetto | Upstream | Qui | Perché |
|---|---|---|---|
| Backend HTTP | Flask | **stdlib `http.server`** | il recipe `flask` di p4a pinna Flask 2.0.3, incompatibile con Werkzeug 3.x; Flask 3.x non ha `setup.py` |
| yt-dlp | eseguibile CLI | **libreria Python in-process** | su Android non esiste un binario `python` → `sys.executable` è vuoto |
| ffmpeg | binario di sistema | **compilato col NDK**, come libreria nativa | il binario glibc viene ucciso da seccomp (`SIGSYS`); inoltre la data dir dell'app è `noexec` |
| UI | browser | **WebView in-app** + GUI Kivy | app autonoma |
| Salvataggio | download del browser | **MediaStore** (o scrittura diretta su API < 29) | una WebView Android non scarica da sola |
| Lingua | inglese | **EN e IT** | scelta a build time (`LANG`) |

## 6. Insidie già risolte (utili se si ricompila)

- `android.entrypoint` è la **classe dell'Activity**, non il file Python
- il container `kivy/buildozer` usa Python 3.14 → venv di p4a con pip rotto
  (per questo si usa ubuntu-22.04 + Python 3.11)
- la build release produce un **AAB** di default → serve
  `android.release_artifact = apk`
- le **classi annidate** jnius richiedono il `$` (`android.os.Build$VERSION`,
  `android.provider.MediaStore$Downloads`)
- l'header `Content-Disposition` è **latin-1**: un titolo con emoji faceva
  fallire la risposta (`RemoteDisconnected`)
- i log applicativi non vanno scritti in `Download/` (li vede l'utente):
  restano nella memoria privata e si esportano su richiesta

## 7. Compilare "a mano" (x86_64)

```bash
# prerequisiti (Debian/Ubuntu x86_64)
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
  autoconf libtool pkg-config zlib1g-dev libncurses-dev cmake \
  libffi-dev libssl-dev build-essential

pip install "buildozer==1.5.0" "cython==0.29.36"

# opzionale: ffmpeg nativo (altrimenti la build lo compila da sola... in CI)
# vedi lo step "Build Android-native ffmpeg/ffprobe (NDK)" nel workflow

buildozer -v android release      # primo run: scarica SDK/NDK (~4 GB)
```

Per firmare l'APK prodotto:

```bash
BT=$HOME/.buildozer/android/platform/android-sdk/build-tools/*/   # ultima versione
"$BT/zipalign" -f 4 bin/*release-unsigned.apk /tmp/aligned.apk
"$BT/apksigner" sign --ks app.keystore --ks-key-alias reclip \
  --ks-pass pass:LA_PASSWORD --key-pass pass:LA_PASSWORD \
  --out bin/reclip-release-signed.apk /tmp/aligned.apk
```

## 8. Licenza

Derivato di [ReClip](https://github.com/averygan/reclip) di averygan — **MIT**.
Il testo originale è in `reclip/LICENSE`.
