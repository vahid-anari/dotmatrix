# Dot Matrix Display

A 64×8 LED matrix (eight 8×8 MAX7219 modules) on an ESP32-C3, controlled over Wi-Fi from an Android app.

- Text with 50 entry/exit effects, including sprites (Pacman, rocket, ...) and four laser effects
- Effects over a text while it stays: wave, sparkle, pulse, border
- Standalone animations: Matrix rain, Matrix reveal, starfield, Game of Life, fireworks, equalizer, snake, running sprite
- The app's editor previews each item, animated, the way the display plays it
- Clock synced from the internet, with automatic daylight saving and night dimming
- Stopwatch and countdown timer that run on the display
- Works on its own after a power cut: the playlist is stored on the device
- Wi-Fi setup from any phone; app and firmware updates from GitHub Releases, installed from the phone

| Folder | Contents |
|---|---|
| [`firmware/`](firmware/) | ESP32-C3 firmware (PlatformIO) |
| [`app/`](app/) | Android app (Flet) |
| [`tools/`](tools/) | `dm.py` command-line client, `fake_device.py` for testing without hardware, example playlists |
| [`docs/`](docs/DESIGN.md) | Design, protocol, roadmap |

## Status

| Milestone | |
|---|---|
| M1: Firmware core | ✅ done, tested on hardware |
| M2: App core | ✅ done, tested on a phone |
| M3: Stopwatch, timer, updates from the app, CI releases | ✅ done, released as v0.2.0 |
| M4: More animations, lasers, overlays, animated preview | ✅ written, tested on the PC (host tests, fake display) |
| M5: Temperature/humidity, weather | planned |

## Downloads

Each version (`v0.1.0`, …) has the Android app and the firmware under [Releases](../../releases), built by GitHub Actions: a push to `main` that raises the version releases it.

## License

MIT, see [LICENSE](LICENSE). Uses [MD_Parola](https://github.com/MajicDesigns/MD_Parola) and [MD_MAX72XX](https://github.com/MajicDesigns/MD_MAX72XX) (LGPL-2.1); the sprite data comes from the MD_Parola examples.
