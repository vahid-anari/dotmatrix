# App

Android app (Python + [Flet](https://flet.dev) 1.0) for the Dot Matrix display.
It talks to the display over Wi-Fi using the protocol in [`../docs/DESIGN.md`](../docs/DESIGN.md) §6.

| Screen | What it does |
|---|---|
| Home | What the display shows now, mode (texts, clock, off), brightness, a quick message |
| Texts | Groups of items (playlists). Play one to send it to the display. Edit items with a live preview on the display |
| Clock | 12/24-hour, seconds, date interval and style, dimming at night |
| Tools | Stopwatch and countdown timer, running on the display |
| Settings | Find or enter the display's address, its name and time zone, Wi-Fi, export and import, updates for the app and the display |

The display stores the group it plays, so it keeps going when the phone is away.
Groups themselves live on the phone, in the app's private storage.

## Run on a computer

```sh
conda activate dotmatrix          # or any Python 3.10+ environment
cd app
pip install "flet[all]==1.0.4" "websockets>=13,<18"
flet run src/main.py              # desktop window
flet run --web src/main.py        # in the browser
```

Without the hardware, start the fake display in another terminal and point the app at it:

```sh
pip install aiohttp
python tools/fake_device.py                       # from the repo root
python tools/fake_device.py --fw 0.1.0            # pretend to be old, to try the firmware update
DM_HOST=127.0.0.1:8080 flet run src/main.py       # or type 127.0.0.1:8080 in Settings
```

## Install on the phone

GitHub builds the APK for you (`.github/workflows/build.yml`):

- After every push to `main`, the APK is under **Actions → the latest run → Artifacts**.
- For a release, tag it: `git tag v0.1.0 && git push origin v0.1.0`. The APK and the firmware appear under **Releases**, where the phone can download and install them directly.

Installing a newer version over the old one keeps your groups. Once installed, the app checks for new releases itself: Home shows a note, and Settings → Updates downloads the new APK or installs new firmware on the display over Wi-Fi.

### Signing key (once)

Android only installs an update over an app signed with the same key. Make one key and give it to GitHub:

```sh
keytool -genkeypair -v -keystore ~/dotmatrix.jks -alias dotmatrix \
        -keyalg RSA -keysize 2048 -validity 10000
base64 -i ~/dotmatrix.jks | pbcopy        # macOS: copies the key as text
```

On GitHub, in the repo: **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | the copied text |
| `ANDROID_KEYSTORE_PASSWORD` | the password you chose |
| `ANDROID_KEY_ALIAS` | `dotmatrix` |

Keep `dotmatrix.jks` and its password safe and **never commit it** (`*.jks` is in `.gitignore`). If the key is lost, the next version can only be installed after uninstalling the app. An app installed before the key existed has to be uninstalled once: export your texts first (Settings → Export) and import them afterwards.

Making a release: set the same version in `app/pyproject.toml` and `APP_VERSION` (`src/ui/app.py`), commit, then tag it (`git tag v0.3.1 && git push origin v0.3.1`). CI refuses a tag that doesn't match.

To build locally instead: `cd app && flet build apk` (the APK ends up in `app/build/apk/`).

## Tests

```sh
cd app && python -m pytest
```

## Code map

| Path | What it does |
|---|---|
| `src/main.py` | Window, bottom navigation, one-second tick for clock previews |
| `src/core/device.py` | WebSocket client: reconnects by itself, request/ack, events |
| `src/core/discovery.py` | Finds the display: last address, `dotmatrix.local`, then a scan of the Wi-Fi subnet |
| `src/core/library.py` | Groups and preferences in one JSON file |
| `src/core/items.py` | Item defaults, readable effect names, the Demo group |
| `src/core/preview.py` | Draws items as LEDs with the firmware's font, at Parola's text position |
| `src/core/player.py` | Plays an item over time for the editor's animated preview (ports of the firmware's effects) |
| `src/core/sprites.py` | Sprite pictures, generated from the firmware by `tools/gen_sprites.py` |
| `src/core/updates.py` | Latest GitHub release, downloads, firmware upload to the display |
| `src/ui/` | One module per screen, plus the shared theme and widgets |

The font is [IBM Plex Sans](https://github.com/IBM/plex) (SIL Open Font License, see `src/assets/IBMPlexSans-OFL.txt`).
