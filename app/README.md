# App

Android app (Python + [Flet](https://flet.dev) 1.0) for the Dot Matrix display.
It talks to the display over Wi-Fi using the protocol in [`../docs/DESIGN.md`](../docs/DESIGN.md) §6.

| Screen | What it does |
|---|---|
| Home | What the display shows now, mode (texts, clock, off), brightness, a quick message |
| Texts | Groups of items (playlists). Play one to send it to the display. Edit items with a live preview on the display |
| Clock | 12/24-hour, seconds, date interval and style, dimming at night |
| Settings | Find or enter the display's address, its name and time zone, Wi-Fi, export and import, versions |

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
python tools/fake_device.py                       # from the repo root
DM_HOST=127.0.0.1:8080 flet run src/main.py       # or type 127.0.0.1:8080 in Settings
```

## Install on the phone

GitHub builds the APK for you (`.github/workflows/build.yml`):

- After every push to `main`, the APK is under **Actions → the latest run → Artifacts**.
- For a release, tag it: `git tag v0.1.0 && git push origin v0.1.0`. The APK and the firmware appear under **Releases**, where the phone can download and install them directly.

Installing a newer version over the old one keeps your groups.

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
| `src/core/preview.py` | Draws items as LEDs with the firmware's font |
| `src/ui/` | One module per screen, plus the shared theme and widgets |

The font is [IBM Plex Sans](https://github.com/IBM/plex) (SIL Open Font License, see `src/assets/IBMPlexSans-OFL.txt`).
