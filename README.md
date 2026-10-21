# Dot Matrix Display

A 64×8 LED matrix (eight 8×8 MAX7219 modules) on an ESP32-C3, controlled over Wi-Fi from an Android app.

- Text with 46 entry/exit effects, including sprites (Pacman, rocket, ...)
- Standalone animations: Matrix rain, Matrix reveal (more coming)
- Clock synced from the internet, with automatic daylight saving and night dimming
- Works on its own after a power cut: the playlist is stored on the device
- Wi-Fi setup from any phone, firmware updates over the air

| Folder | Contents |
|---|---|
| [`firmware/`](firmware/) | ESP32-C3 firmware (PlatformIO) |
| `app/` | Android app (Flet), coming in milestone 2 |
| [`tools/`](tools/) | `dm.py` command-line client and example playlists |
| [`docs/`](docs/DESIGN.md) | Design, protocol, roadmap |

## Status

| Milestone | |
|---|---|
| M1: Firmware core | ✅ written, compiles; hardware test pending |
| M2: App core | next |
| M3: Stopwatch, timer, OTA from app, CI releases | planned |
| M4: More animations and text overlays | planned |
| M5: Temperature/humidity, weather | planned |

## License

MIT, see [LICENSE](LICENSE). Uses [MD_Parola](https://github.com/MajicDesigns/MD_Parola) and [MD_MAX72XX](https://github.com/MajicDesigns/MD_MAX72XX) (LGPL-2.1); the sprite data comes from the MD_Parola examples.
