# Dot Matrix Display — Design

Status: v0.5 (2026-10-21), M1–M3 done and tested on hardware (release v0.2.0); M4 written

A 64×8 LED matrix (eight 8×8 MAX7219 modules) driven by an ESP32-C3, controlled from an Android app written in Python with Flet. This document records the decisions made so far and is the reference for both halves of the project.

---

## 1. Goals

- Show text with entry/exit effects, a clock, and later temperature, humidity, and weather.
- Run on its own: after a power cut it shows the last playlist without the phone.
- Stay up for months without freezing.
- Make new display modes easy to add without touching the rest of the code.
- Easy installation and updates for both the firmware (over Wi-Fi) and the app (APK from GitHub Releases).

## 2. Decisions

| Topic | Decision | Why |
|---|---|---|
| Phone | Android first; Flet keeps iOS possible later | Current phone; APK sideloading is simple |
| Link | Wi-Fi only (BLE dropped) | Always on mains power, so BLE's low power doesn't matter; Wi-Fi brings NTP, weather, OTA, and simpler code |
| Discovery | mDNS: `dotmatrix.local` | No IP addresses to type |
| First setup | ESP32 opens its own access point with a captive setup page | Works from any phone, even without the app |
| Time | NTP + POSIX time zone (`America/Toronto`, DST automatic) | Replaces manual "Set Time" and the `RTC_TIME` library |
| Storage | ESP32 stores the **active playlist** and settings (LittleFS); the phone stores the **library** of groups | Device works alone; phone is the editor |
| Protocol | JSON over WebSocket | One message per action instead of ten `param=value` writes |
| Battery reading | Removed | Device is always on a charger; can be re-added later |
| Firmware tooling | PlatformIO (VS Code or `pio` CLI) | Pinned library versions, reproducible builds |
| App framework | Flet 1.0 | Same toolchain as Daftarche |
| Language on display | English/ASCII only | Persian not needed |
| Playlist items | Text items and standalone animation items | Effects can be the message itself, not only transitions |
| Limits | 100 items per playlist, 128 characters per text | Fits comfortably in RAM and LittleFS |
| License | MIT for project code; MD_Parola and sprite data stay LGPL-2.1 | Simple, permissive, compatible |

## 3. Hardware

| Part | Detail |
|---|---|
| MCU | ESP32-C3 Super Mini |
| Display | 8 × MAX7219 8×8 modules, FC-16 type, chained (64×8) |
| Display SPI | CS = GPIO 7, hardware SPI (SCK = GPIO 4, MOSI = GPIO 6) |
| Status LED | GPIO 8 (active low) |
| Power | 5 V USB charger, always connected |
| Planned | Temperature/humidity sensor on I²C (e.g. SHT31 or AHT20) |

Wi-Fi TX power is capped at 8.5 dBm, because many C3 Super Mini boards have a weak antenna layout and drop the link at full power.

## 4. Firmware architecture

```
firmware/
├── platformio.ini
└── src/
    ├── main.cpp            setup(), loop(), watchdog
    ├── config.h            pins, defaults, version
    ├── display/            Display wrapper over MD_Parola, effects table, fonts, sprites,
    │                       TextFx (our own text effects) and Overlay (effects over static text, §4a)
    ├── animations/         all implementing Animation (§4a): MatrixRain, the others in Scenes
    ├── modes/              one file per mode, all implementing Mode
    │   ├── Mode.h          interface: begin(), loop(), end(), handle(json)
    │   ├── TextMode        plays the playlist
    │   ├── ClockMode       time, date every N seconds
    │   ├── StopwatchMode   runs on the device
    │   ├── TimerMode       countdown
    │   └── SensorMode      (later) temperature/humidity
    ├── net/                Wi-Fi, captive setup portal, mDNS, NTP, OTA
    ├── api/                WebSocket server, JSON command router
    └── storage/            LittleFS: playlist.json, settings.json
```

A **mode** owns the display while it is active. The mode manager switches modes, saves the current mode to settings, and restores it on boot. Adding a mode means adding one class and registering it.

### 4a. Animations and overlays

A playlist can hold two kinds of items: **text** (MD_Parola, with in/out effects as before) and **animation** (a standalone scene that runs for a set time). TextMode plays both in order, so a playlist can be "10 s Matrix rain → 'Welcome' → Starfield".

Animations draw directly on the 64×8 frame buffer through MD_MAX72XX (Parola's underlying driver) and implement a small interface:

```cpp
class Animation {
 public:
  virtual void begin(Frame& f, const JsonObject& params) = 0;
  virtual bool step(Frame& f, uint32_t now) = 0;  // false when finished early
  virtual uint16_t frameMs() const = 0;           // frame interval
};
```

Adding an animation means one file plus one line in the registry. Planned animations:

| ID | Description |
|---|---|
| `matrix_rain` | Columns of dots fall at different speeds |
| `matrix_reveal` | Matrix rain where the item's text gradually appears and stays |
| `starfield` | Stars move outward from the centre |
| `life` | Conway's Game of Life from a random seed, reseeds when stable |
| `fireworks` | Rocket rises and bursts |
| `equalizer` | Bars bounce up and down |
| `snake` | Self-playing snake |
| `sprite_run` | A sprite (Pacman, rocket, ...) crosses the whole display (`params.sprite`) |

`params.density` means drops (Matrix), stars (starfield), % of cells alive at the start (life) or rockets in the air (fireworks); `params.speed` is the frame time in ms. New animations go at the end of the registry, so stored indexes keep their meaning.

**Our own text effects.** Parola has no laser, so these are drawn frame by frame by `display/TextFx`. Each works as an entry effect, and played backwards as an exit effect:

| ID | Description |
|---|---|
| `laser_write` | A beam from the bottom-left corner draws the text column by column (out: erases it in the same order) |
| `laser_scan` | A vertical beam with sparks sweeps across; the text appears behind it (out: disappears ahead of it) |
| `laser_cut` | A cutting dot traces each letter stroke by stroke (out: cuts it away) |
| `laser_beam` | Like `laser_write`, but the beam comes level from the right edge, always at the height of the dot it draws |

Write, beam and cut draw one pixel per step, but never take more than 64, 64 and 80 steps: a text with more lit pixels gets several per step, so long texts don't take ages. Scan always takes 66 steps. `speed_in`/`speed_out` are the ms per step, as for Parola effects. On a text wider than the display, the lasers work on the part that's showing.

**How a text item plays.** Without our effects or an overlay, Parola plays the whole item (in → pause → out), as before. Otherwise it plays in three phases, each drawn by whoever does it: in (Parola, or TextFx), pause (our frames, with the overlay), out (Parola, or TextFx). Our frames put the text exactly where Parola does (`MD_PZone::calcTextLimits`: centred text leans right by half a column; and like Parola, no gap after an empty glyph, such as the second byte of some UTF-8 letters), so the hand-overs don't show. A text wider than the display rests at the left edge, except after `scroll_left` in: Parola stops once the last column has come in, so the end of the text is showing. An overlay needs the text to fit on the display; on a longer text it's ignored. "None" as an entry effect shows the text at once (Parola's `PA_NO_EFFECT` would skip it).

**Overlays** run on top of static text after the in-effect has finished, during the `pause`:

| ID | Description |
|---|---|
| `wave` | Letters bob up and down one by one |
| `sparkle` | Random pixels twinkle over the text |
| `pulse` | Brightness breathes up and down |
| `border` | A line of 6 dots runs around the edge |

Hardware limit: MAX7219 brightness is per 8×8 module, not per pixel. Effects like the fading trail in Matrix rain are faked with pixel flicker, not dimming.

### Libraries

| Old | New |
|---|---|
| `VA_Parola` | Rewritten as `display/`, still on top of upstream **MD_Parola** (not a fork) |
| `Sprite` | Kept as data in `display/sprites` (from the MD_Parola examples, LGPL) |
| `RTC_TIME` + `ESP32Time` | ESP-IDF time (`configTzTime`) + `millis()`-based scheduler |
| `ItemsList` | `std::vector<Item>` |
| `SplitString` | Replaced by ArduinoJson |
| `LED` | Kept |
| BLE stack | `ESPAsyncWebServer` + `AsyncTCP` (WebSocket, setup page, OTA upload), `ESPmDNS`, `DNSServer` |

### Reliability (fixes the "clock freezes after weeks" bug)

Likely causes found in v8:

1. `updateText()` passes `String::c_str()` to `MD_Parola::setTextBuffer()`. Parola keeps the pointer, so when the `String` reallocates, the display reads freed memory.
2. Heap fragmentation from creating `String`s every second (time, date, BLE values, serial logs).
3. Long-uptime instability in the BLE stack.
4. No watchdog to recover from a hang.

Rules for v9:

- The display text lives in a fixed `char` buffer owned by `Display`; Parola never points into a `String`.
- No `String` building in the main loop; use `snprintf` into fixed buffers.
- No `delay()` in the loop; all waits are non-blocking `millis()` timers (written as `now - last >= interval`, which is overflow-safe).
- Task watchdog enabled. If the loop stalls, the device reboots and restores its state from LittleFS.
- The `state` event (below) reports `uptime`, `free_heap`, and `min_free_heap`, so leaks show up in the app long before they cause trouble.

## 5. Networking

```
power on
  ├─ saved Wi-Fi?  ── no ──▶  AP "DotMatrix-XXXX" + captive setup page (192.168.4.1)
  │                                └─ user enters SSID/password ─▶ save ─▶ reboot
  └─ yes ─▶ join home Wi-Fi (retry 20 s)
              ├─ ok   ─▶ mDNS dotmatrix.local, NTP sync, WebSocket ready
              └─ fail ─▶ AP mode as above, still retrying home Wi-Fi
```

- NTP syncs at boot and then hourly. Between syncs the internal clock runs on its own, and if the internet drops the clock keeps going.
- The device shows its IP or setup network name on the matrix when it changes state, so the user can always see what to connect to.
- OTA: the app uploads a `.bin` to `POST /update`, and `ArduinoOTA` is also enabled for development.

## 6. Protocol (v1)

Transport: WebSocket at `ws://dotmatrix.local/ws`, text frames, one JSON object per frame.

**App → device** — every command carries an `id` so the app can match the reply.

```jsonc
{"id": 1, "cmd": "get_state"}
{"id": 2, "cmd": "set_mode", "mode": "text"}          // text | clock | stopwatch | timer | off
{"id": 3, "cmd": "set_playlist", "name": "Home", "items": [ITEM, ...]}
{"id": 3, "cmd": "get_playlist"}                      // → playlist event
{"id": 4, "cmd": "preview", "item": ITEM}             // live edit; shown until preview_end,
                                                      // the client disconnects, or 10 min pass
{"id": 5, "cmd": "preview_end"}
{"id": 6, "cmd": "set_settings", "settings": {...}}   // partial update, see below
{"id": 6, "cmd": "get_settings"}                      // → settings event
{"id": 7, "cmd": "stopwatch", "action": "start"}      // start | pause | reset | show
{"id": 8, "cmd": "timer", "action": "start", "seconds": 300}  // start [seconds] | set seconds |
                                                      // pause | reset | show
{"id": 9, "cmd": "set_wifi", "ssid": "...", "password": "..."}
{"id": 10, "cmd": "reboot"}
```

**Device → app**

```jsonc
{"evt": "hello", "proto": 1, "fw": "0.2.0", "name": "dotmatrix", "max_items": 100, "max_text": 128,
 "effects": ["no_effect", ...], "animations": ["matrix_rain", ...],
 "overlays": ["none", "wave", ...], "sprites": ["pacman", ...],     // since 0.3.0
 "modes": ["text", "clock", "off", "stopwatch", "timer"]}
{"evt": "settings", "settings": {...}}                // after hello, and whenever settings change
{"evt": "ack", "id": 3, "ok": true}
{"evt": "ack", "id": 3, "ok": false, "error": "item 4: unknown animation"}
{"evt": "playlist", "id": 3, "name": "Home", "items": [ITEM, ...]}
{"evt": "state", "mode": "clock", "playlist": "Home", "items": 12, "index": 3, "previewing": false,
 "time": "2026-10-21 14:05:09", "brightness": 6, "night": false, "wifi": "online",
 "ip": "192.168.1.50", "rssi": -58, "uptime": 123456, "free_heap": 182000,
 "min_free_heap": 170000, "last_reset": "power_on",
 "stopwatch": {"ms": 83120, "running": true},
 "timer": {"remaining_ms": 41000, "total_ms": 300000, "running": true, "done": false}}
```

Stopwatch and timer commands switch the display to that mode (not remembered across a reboot). Both keep running in the background when another mode is shown. When the timer reaches zero the display switches to it and blinks for a minute. Between `state` messages the app counts on from the last values, so its preview runs smoothly without extra traffic.

The device sends `state` when it changes, plus once every 5 s. The `hello` lists let the app build its effect, animation, overlay and sprite pickers from what the firmware supports; firmware without `overlays` hides the overlay picker.

HTTP on port 80: `/` setup page, `/api/status`, `/api/scan`, `POST /api/wifi` (form: `ssid`, `password`), `POST /update` (firmware `.bin`). The setup network is `DotMatrix-XXXX` with password `dotmatrix`.

**ITEM** — `type` is `text` (default) or `animation`

```jsonc
{
  "type": "text",
  "text": "Hello",
  "effect_in": "scroll_left",  "effect_out": "scroll_left",
  "speed_in": 50, "speed_out": 50,   // ms per frame
  "pause": 400,                      // ms shown between in and out
  "gap": 100,                        // ms blank before the next item (was textDelayIn)
  "align": "center",                 // left | center | right
  "invert": false,
  "brightness": 8,                   // 0–15, optional; falls back to global
  "overlay": "sparkle"               // optional: none | wave | sparkle | pulse | border (§4a)
}
```

```jsonc
{
  "type": "animation",
  "animation": "matrix_reveal",
  "duration": 10000,                 // ms
  "text": "Welcome",                 // used by animations that show text
  "params": {"density": 3, "speed": 60, "sprite": "rocket"},  // all optional, see §4a
  "brightness": 8
}
```

Effect IDs are snake_case (`no_effect`, `print`, `scroll_up`, ... `sprite_pacman`, `sprite_wave`, `laser_write`), and the app maps them to readable names. New effects are added at the end of the table so stored indexes keep their meaning.

**Settings**

```jsonc
{
  "brightness": 8,
  "clock": {"format_24h": true, "seconds": true, "date_every": 10, "date_format": "%a %b %d"},
  "night": {"enabled": true, "from": "23:00", "to": "07:00", "brightness": 1},
  "timezone": "EST5EDT,M3.2.0,M11.1.0"
}
```

## 7. App

```
app/
├── pyproject.toml
└── src/
    ├── main.py
    ├── core/       device client (WebSocket, reconnect), protocol models, library storage
    └── ui/         one module per screen, shared widgets, theme
```

Screens (bottom navigation bar):

1. **Home**: connection state, what's showing now (drawn as LEDs), mode (texts / clock / off), brightness, a quick message shown as a preview.
2. **Texts**: groups → items → editor. Drag to reorder, duplicate, "play this group" (sends `set_playlist`). The editor uses `preview` so changes show live on the matrix.
3. **Clock**: 12/24 h, seconds, date interval and format, night dimming.
4. **Tools**: stopwatch and countdown timer (presets and a custom length), both running on the device.
5. **Settings**: device address (found automatically, or typed), name, time zone, Wi-Fi, library export/import, and updates for the app and the display's firmware.

Storage on the phone: one JSON file in `FLET_APP_STORAGE_DATA`. The Demo group (one item per effect) is built in.

Look: aluminium greys, circuit-board green for controls, and red only in the LED previews, which use the firmware's font so they match the display column for column.

Finding the display: the last address that worked, then `dotmatrix.local`, then a scan of the phone's /24 subnet for `/api/status` (no special Android permissions). After three failed reconnects the app looks again, in case the router gave the display a new address.

**Updates (M3).** Every release `vX.Y.Z` builds the APK and the firmware with that same version (CI fails if `app/pyproject.toml` and `APP_VERSION` disagree, and stamps `FW_VERSION` into the firmware). A push to `main` whose version has no tag yet is a release: CI creates the tag with the release, so releasing needs no tag push. The app reads the latest release from the GitHub API at start and when asked:

- a newer APK: the phone's browser downloads it, and installing it over the old app keeps the library;
- newer firmware: the phone downloads `dotmatrix-firmware.bin`, checks it is an ESP32 image, and POSTs it to the display's `/update`. The ESP32 writes it to the spare OTA slot and only switches to it once the whole image has been verified, so an interrupted upload leaves the old firmware running.

Local builds report `X.Y.Z-dev`, which sorts just below release `X.Y.Z`.

**Animated preview (M4).** The editor's LED strip plays the item over and over, the way the display will (`core/player.py`, about 25 frames a second, only while the editor is open; lists stay still). The lasers, overlays and animations are ported line by line from the firmware (the random ones look alike, not identical). Parola's print, scroll (also of texts too long for the display), wipe, opening/closing, slice and sprite effects move step for step like Parola's; its other effects (mesh, fade, dissolve, blinds, grow, scan, diagonal scroll) are close likenesses, and the editor says so under the preview. The preview draws the UTF-8 bytes of the text, as the display does. Playing a group on older firmware leaves out the animations it doesn't have (it would refuse the whole list) and says so. `tests/test_core.py` checks that the app's lists of effects, animations, overlays and sprites, and the default animation speeds, match the firmware source, and `tools/gen_sprites.py` copies the sprite pictures across. Each new firmware effect gets its app preview in the same change, so the two never drift apart.

## 8. Development and release

- `tools/fake_device.py` is a Python WebSocket server that speaks protocol v1, so the app can be developed and tested without the hardware.
- GitHub Actions build the firmware (`pio run`) and the APK (`flet build apk`) on every push. A push that raises the version in `app/pyproject.toml` (or a pushed `vX.Y.Z` tag) publishes both to a GitHub Release tagged `vX.Y.Z`.
- Firmware and app versions are tracked separately. Both check `proto` in `hello` and warn if they don't match.

## 9. Roadmap

| Milestone | Scope |
|---|---|
| **M1: Firmware core** | PlatformIO project, display wrapper, TextMode + ClockMode, animation framework with `matrix_rain` and `matrix_reveal`, LittleFS, Wi-Fi + setup portal, mDNS, NTP, WebSocket API, watchdog |
| **M2: App core** | Device client, Home, Texts (+ live preview, animation items), Clock, Settings, fake device |
| **M3: Extras** | Stopwatch and timer on the device, OTA from the app, app update check, CI releases (night dimming already came with M1) |
| **M4: Effects** | Remaining animations (`starfield`, `life`, `fireworks`, `equalizer`, `snake`, `sprite_run`), overlays (`wave`, `sparkle`, `pulse`, `border`), laser effects (`laser_write`, `laser_scan`, `laser_cut`, `laser_beam`). Animated preview in the app editor (§7) |
| **M5: Sensors** | Temperature/humidity mode, weather from the internet |

## 10. Open questions

- **Security on the home network:** firmware upload (`/update`, ArduinoOTA) and Wi-Fi changes have no password yet, so anyone on the same Wi-Fi could reflash the device. Proposal: a device PIN shown on the display when the app pairs for the first time.
- Repository name (candidates: `dotmatrix-display`, `pixelboard`, `ledline`, `glimmer`, `marquee32`).
- If there will ever be more than one device, each needs its own mDNS name (e.g. `dotmatrix-kitchen.local`).
