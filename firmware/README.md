# Firmware

ESP32-C3 firmware for the 64×8 dot matrix display (8 × MAX7219, FC-16 modules).
See [`../docs/DESIGN.md`](../docs/DESIGN.md) for the architecture and protocol.

## Build and flash

Needs [PlatformIO](https://platformio.org/) (the VS Code extension, or `pip install platformio`).

```sh
cd firmware
pio run -t upload        # build + flash over USB
pio device monitor       # serial log, 115200 baud
```

The first build downloads the ESP32 toolchain and libraries, which takes a few minutes.

Later updates can go over Wi-Fi:

```sh
pio run -t upload --upload-port dotmatrix.local
```

## Wiring

| Display | ESP32-C3 |
|---|---|
| VCC | 5V |
| GND | GND |
| DIN | GPIO 6 (MOSI) |
| CS | GPIO 7 |
| CLK | GPIO 4 (SCK) |

## First start

1. After flashing, the display scrolls **"Setup: join Wi-Fi DotMatrix-XXXX password dotmatrix"**.
2. Join that network from your phone. The setup page should open by itself; if not, open `http://192.168.4.1`.
3. Pick your home network, enter its password, and press **Save and connect**.
4. The display restarts, joins your Wi-Fi, and scrolls its address once: `dotmatrix.local  192.168.x.x`.

If the home network can't be reached for 20 s, the setup network comes back automatically while the device keeps retrying.

## Trying it without the app

`tools/dm.py` sends protocol commands from a computer on the same network:

```sh
pip install websockets
python tools/dm.py state
python tools/dm.py playlist tools/examples/demo.json
python tools/dm.py mode clock
python tools/dm.py settings '{"clock":{"date_every":20},"night":{"enabled":true,"from":"23:00","to":"07:00","brightness":0}}'
python tools/dm.py watch
```

## Host tests

The item/settings parsing and the animations also build and run on a PC:

```sh
pio pkg install                          # fetches ArduinoJson into .pio/libdeps
./test_host/run.sh                       # or: ./test_host/run.sh --show  (ASCII frames)
```

## Code map

| Path | What it does |
|---|---|
| `src/App.*` | Owns everything: modes, protocol commands, saving, watchdog |
| `src/display/` | MD_Parola wrapper (text + effects), direct frame drawing, sprites |
| `src/animations/` | Standalone animations; add one in `Registry.cpp` |
| `src/modes/` | Text playlist, clock (off mode lives in `App.*`) |
| `src/model/` | `Item` and `Settings` with their JSON format |
| `src/net/` | Wi-Fi + setup portal, mDNS, NTP, OTA, HTTP/WebSocket server |
| `src/storage/` | LittleFS (playlist, settings) and NVS (Wi-Fi) |

## Troubleshooting

- **Build fails with `riscv32-esp-elf-g++: command not found`** (seen on macOS): the compiler was unpacked one folder too deep. Move the contents of `~/.platformio/packages/toolchain-riscv32-esp/riscv32-esp-elf/` up into `~/.platformio/packages/toolchain-riscv32-esp/` (same for `~/.platformio/tools/toolchain-riscv32-esp/`), then build again.
- **The monitor misses the startup lines:** the C3's USB port reconnects on reset, so the first second of log is lost. Messages after that (Wi-Fi, clients) appear normally.
- **`dotmatrix.local` doesn't resolve sometimes:** use the IP the display shows after connecting: `python tools/dm.py --host 192.168.x.x state`, or `export DM_HOST=192.168.x.x` once per terminal.
- **Animations or the clock look mirrored** (text effects fine): set `DISPLAY_FLIP_X = true` in `src/config.h`.
- **Wi-Fi drops or won't connect:** many C3 Super Mini boards have a weak antenna, so TX power is already lowered to 8.5 dBm (`WIFI_TX_POWER`). Keep the board away from the display's power wires.
- **The state shows `"last_reset": "watchdog"`:** the main loop stalled and the device restarted itself. Please note what it was showing at the time.
