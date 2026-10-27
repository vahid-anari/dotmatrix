# Dot Matrix

[![build](https://github.com/vahid-anari/dotmatrix/actions/workflows/build.yml/badge.svg)](https://github.com/vahid-anari/dotmatrix/actions/workflows/build.yml)
[![release](https://img.shields.io/github/v/release/vahid-anari/dotmatrix)](https://github.com/vahid-anari/dotmatrix/releases/latest)
![License](https://img.shields.io/badge/license-MIT-green)

**Dot Matrix** is a 64 × 8 LED display for the desk or the wall, built from an
ESP32-C3 and eight MAX7219 8×8 modules, and an Android app that controls it over
Wi-Fi. It plays a list of texts with entry and exit effects (scrolling, sprites like
Pacman, and four laser effects of its own), effects over a text while it stays
(wave, sparkle, pulse, border) and animations of their own (Matrix rain, a
starfield, the Game of Life, fireworks, an equalizer, a snake that plays by itself).
It also shows the time, with the date and the weather outside dropping in now and
then, and runs a stopwatch and a countdown timer.

The playlist is stored on the display, so it keeps playing on its own when the phone
is away and comes back by itself after a power cut. The time comes from the internet,
with daylight saving and dimming at night.

<img src="https://raw.githubusercontent.com/vahid-anari/dotmatrix/main/case/images/front.png" width="700" alt="The display in its 3D-printed desk case, showing DotMatrix">

## Installation

**The display.** An ESP32-C3 Super Mini, two MAX7219 4-in-1 boards (FC-16 type) and
five wires; [`docs/HARDWARE.md`](docs/HARDWARE.md) has the parts, the connections and
some tips, and [`case/`](case/) a 3D-printable desk case.

<img src="https://raw.githubusercontent.com/vahid-anari/dotmatrix/main/docs/wiring.svg" width="700" alt="Wiring: VCC to 5V, GND to G, DIN to GPIO 6, CS to GPIO 7, CLK to GPIO 4">

The firmware goes on once over USB, with [PlatformIO](https://platformio.org):

```
cd firmware
pio run -t upload
```

After that, new firmware is installed from the app over Wi-Fi. More in
[`firmware/README.md`](firmware/README.md).

**The app.** Download the APK from the newest
[release](https://github.com/vahid-anari/dotmatrix/releases/latest) on the phone and
open it to install (Android asks once to allow installs from the browser). The app
checks for new versions itself: Home shows a note, and Settings → Updates downloads
the new app or installs the new firmware on the display.

## Use

The first time, the display scrolls the name and password of its own Wi-Fi network.
Join it with the phone, and a page opens to choose your home Wi-Fi; from then on the
display is on your network as `dotmatrix.local`, and the app finds it by itself.

Texts holds groups of items: each group is a playlist, and ▶ sends it to the
display. An item is a text, with how it comes in and leaves, how long it stays, what
plays over it meanwhile, its alignment and brightness, or an animation that runs for
a set time. The editor's LED strip plays the item over and over the way the display
will, and with "Show on the display while editing" the display plays it too. Home
shows what the display is doing, switches between texts, clock and off, sets the
brightness and sends a quick message. Clock sets 12- or 24-hour time; whether the date
and the weather come by, one after the other, how often, and whether they drop in from
the top or scroll across; the place for the weather; and the hours of night dimming. Tools runs the stopwatch and the timer on the display: they keep going
when the phone is put away, and the timer takes over the display and blinks when it
reaches zero. Settings has the connection, the display's name and time zone, the
app's look (light, dark or as the phone is set, and the LED colour of your display),
export and import of your texts, and updates.

Without the app, [`tools/dm.py`](tools/dm.py) does the same from a terminal, for
example `python tools/dm.py say "Hello"` or `python tools/dm.py watch`.

## Your data

The display keeps its playlist and settings in its own flash memory; the Wi-Fi
password stays on the display. The app keeps your groups in one file in its private
storage on the phone; Settings → Your texts exports them to a file and imports them
again, for a new phone or a backup. Nothing goes anywhere else: the only outside
services are GitHub, for updates, and Open-Meteo, which the display asks for the
weather of the place you chose.

## Development

```
cd app && python -m pytest               # app tests
cd firmware && ./test_host/run.sh        # firmware tests on the computer
python tools/fake_device.py              # a pretend display, for the app without hardware
DM_HOST=127.0.0.1:8080 flet run app/src/main.py
```

[`docs/DESIGN.md`](docs/DESIGN.md) describes how it all works: the firmware's parts,
the protocol between app and display, and the roadmap. GitHub Actions builds the
firmware and the APK on every push; a push that raises the version in
`app/pyproject.toml` (and `APP_VERSION`) publishes them as a release, which the app
then offers as an update; [`CHANGELOG.md`](CHANGELOG.md) lists what each version
changed. Planned next: a temperature and humidity sensor, automatic
brightness from a light sensor, and signed firmware updates.

## Support

This is a free project I work on in my spare time. If you like it, you can [buy me a coffee](https://buymeacoffee.com/vahidanarim) ☕

## License

MIT License. See [LICENSE](LICENSE). Uses [MD_Parola](https://github.com/MajicDesigns/MD_Parola)
and [MD_MAX72XX](https://github.com/MajicDesigns/MD_MAX72XX) (LGPL-2.1); the sprite pictures
come from the MD_Parola examples.

## Author

Vahid Anari ·
[GitHub](https://github.com/vahid-anari) ·
[LinkedIn](https://www.linkedin.com/in/vahid-anari/)
