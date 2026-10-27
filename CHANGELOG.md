# Changelog

Released with tags `vX.Y.Z`; each release carries the signed APK and the firmware,
which the app offers as updates. The version is the app's; the firmware takes the
same number when it changes too.

## 0.5.1 — 2026-10-27

The app now looks and behaves like Daftarche and Spoolbook:

- The name stays at the top of every tab, with the connection as a small line under
  it (a tap opens Settings), instead of a heading on each tab.
- Swiping left and right moves between the tabs, and the bottom bar follows.
- Back goes to Home from the other tabs; on Home it asks "Press Back again to exit",
  and a second Back within two seconds leaves the app. An open group or the editor
  closes first.
- Every list ends with room to scroll its last row clear of the bottom bar.
- Messages stay three seconds.
- Settings → About also names the author, the licence (MIT) and where the weather
  comes from (Open-Meteo).

## 0.5.0 — 2026-10-26

- The clock's date and weather come one after the other, at one interval for both;
  each can be switched off.
- They drop in from the top, stay a few seconds (1 to 10 s, adjustable) and go
  back up, with the time sliding away and back; or they scroll across as before.
- The display uses short weather words, so even "-12°C Cloudy" fits.
- Older settings and older apps keep working: the two old intervals are still read
  and reported.
- The night brightness slider no longer calls 0 "Off": it is the dimmest level.

## 0.4.2 — 2026-10-22

- A new app version downloads in the phone's browser, which shows its progress and
  opens the APK when it is done (the in-app page stayed on "Downloading…").

## 0.4.1 — 2026-10-22

- The previews can be drawn in the colour of your display's LEDs: red, green, blue,
  yellow or white (Settings → Appearance).

## 0.4.0 — 2026-10-21

- The weather outside in the clock: with a place chosen (Clock → Weather, by name),
  the display fetches the temperature and the weather from Open-Meteo every 15
  minutes and shows it like the date ("8°C Rain"), in °C or °F. Either can be Never.
- The app's look: Phone (as the phone is set), Light or Dark.

## 0.3.1 — 2026-10-21

- A fourth laser effect: a level beam from the right edge, at the height of the dot,
  draws the text.

## 0.3.0 — 2026-10-21

- Laser effects of our own (write, scan and cut), each coming in and, played
  backwards, going out.
- Effects over a text while it stays: wave, sparkle, pulse, border.
- New animations: a starfield, the Game of Life, fireworks, an equalizer, a snake
  that plays by itself, and a running sprite.
- The editor's LED strip plays the item, animated, the way the display will.
- On older firmware, animations it doesn't have are left out of a playlist, with a
  message.

## 0.2.0 — 2026-10-21

- A stopwatch and a countdown timer on the display (the new Tools tab). They keep
  running with the phone away; the timer comes to the front and blinks at zero.
- Updates: Settings → Updates checks GitHub for new versions, downloads the new app
  or installs new firmware on the display over Wi-Fi; Home shows when one is there.
- A new firmware that fails soon after starting rolls back to the old one.
- The APK is signed with one fixed key, so updates install over the old app.

## 0.1.1 — 2026-10-21

- Making a new group no longer leaves its dialog stuck on the Texts tab.
- The APK is built for 64-bit phones only, a third of the size.

## 0.1.0 — 2026-10-21

- The first version. The display: an ESP32-C3 with eight MAX7219 modules that plays
  a list of texts with entry and exit effects, and animations; the time from the
  internet with daylight saving and night dimming; its own Wi-Fi to set it up; the
  playlist kept through a power cut.
- The app: Home (what the display shows, drawn as LEDs; texts, clock or off;
  brightness; a quick message), Texts (groups as playlists, items to drag into
  order, an editor that can show on the display as you edit), Clock and Settings
  (find the display, its name and time zone, export and import of your texts).
- `tools/dm.py` does the same from a terminal; `tools/fake_device.py` is a pretend
  display for working on the app without hardware.
