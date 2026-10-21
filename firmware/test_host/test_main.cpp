// Host tests for the parts of the firmware that don't need hardware:
// item/settings JSON, and the Matrix animations (printed as ASCII).
//
// Run:  ./test_host/run.sh          (add --show to print animation frames)
#include <cstdio>
#include <string>

#include "../src/animations/Registry.h"
#include "../src/animations/Animation.h"
#include "../src/display/Effects.h"
#include "../src/display/Overlay.h"
#include "../src/display/TextFx.h"
#include "../src/model/Item.h"
#include "../src/model/Settings.h"
#include "../src/modes/TimeFormat.h"

static int failures = 0;
#define CHECK(cond)                                                     \
  do {                                                                  \
    if (!(cond)) {                                                      \
      std::printf("  FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond);    \
      failures++;                                                       \
    }                                                                   \
  } while (0)

static bool showFrames = false;

static void printFrame(const Frame& f) {
  for (int y = 0; y < DISPLAY_HEIGHT; y++) {
    std::putchar('|');
    for (int x = 0; x < DISPLAY_WIDTH; x++) std::putchar(f.get(x, y) ? '#' : ' ');
    std::puts("|");
  }
}

static bool parseItem(const char* json, Item& it, const char*& err) {
  JsonDocument doc;
  if (deserializeJson(doc, json)) return err = "bad json", false;
  return itemFromJson(doc.as<JsonObjectConst>(), it, err);
}

static void testItems() {
  std::puts("items");
  Item it;
  const char* err = nullptr;

  CHECK(parseItem(R"({"text":"Hello","effect_in":"slice","effect_out":"sprite_pacman",
                     "speed_in":20,"pause":900,"align":"left","invert":true,"brightness":3})",
                  it, err));
  CHECK(strcmp(it.text, "Hello") == 0);
  CHECK(strcmp(effectAt(it.effectIn).id, "slice") == 0);
  CHECK(strcmp(effectSpriteName(it.effectOut), "pacman") == 0);
  CHECK(it.speedIn == 20 && it.speedOut == 50 && it.pause == 900);
  CHECK(it.align == Align::Left && it.invert && it.brightness == 3);

  // Round trip through JSON gives the same item.
  JsonDocument doc;
  itemToJson(it, doc.to<JsonObject>());
  Item back;
  CHECK(itemFromJson(doc.as<JsonObjectConst>(), back, err));
  CHECK(strcmp(back.text, it.text) == 0 && back.effectOut == it.effectOut && back.invert);

  // Animation item.
  CHECK(parseItem(R"({"type":"animation","animation":"matrix_reveal","duration":8000,
                     "text":"Hi","params":{"density":12}})",
                  it, err));
  CHECK(it.type == ItemType::Animation && it.duration == 8000 && it.density == 12);
  CHECK(strcmp(animationId(it.animation), "matrix_reveal") == 0);

  // Errors.
  CHECK(!parseItem(R"({"type":"animation","animation":"nope"})", it, err));
  CHECK(strcmp(err, "unknown animation") == 0);
  CHECK(!parseItem(R"({"type":"video"})", it, err));
  std::string longText(MAX_TEXT + 1, 'x');
  std::string j = "{\"text\":\"" + longText + "\"}";
  CHECK(!parseItem(j.c_str(), it, err) && strcmp(err, "text too long") == 0);

  // Whole numbers sent as floats (Python / Flet sliders) are accepted.
  CHECK(parseItem(R"({"speed_in":20.0,"pause":1234.6,"brightness":8.0})", it, err));
  CHECK(it.speedIn == 20 && it.pause == 1235 && it.brightness == 8);

  // Out-of-range values are clamped, unknown effects fall back to no_effect.
  CHECK(parseItem(R"({"speed_in":0,"brightness":99,"effect_in":"zzz"})", it, err));
  CHECK(it.speedIn == 1 && it.brightness == 15 && it.effectIn == 0);

  // M4: lasers, overlays, sprite_run's sprite. Old effect indexes don't move.
  CHECK(effectIndex("sprite_hourglass") == 45 && effectIndex("laser_write") == 46);
  CHECK(effectIndex("laser_beam") == 49 && effectAt(49).fx == FxKind::LaserBeam);
  CHECK(parseItem(R"({"text":"Hi","effect_in":"laser_cut","effect_out":"laser_scan","overlay":"wave"})", it, err));
  CHECK(effectAt(it.effectIn).fx == FxKind::LaserCut && effectAt(it.effectOut).fx == FxKind::LaserScan);
  CHECK(strcmp(overlayId(it.overlay), "wave") == 0);
  doc.clear();
  itemToJson(it, doc.to<JsonObject>());
  CHECK(strcmp(doc["overlay"] | "", "wave") == 0 && strcmp(doc["effect_in"] | "", "laser_cut") == 0);
  CHECK(parseItem(R"({"text":"Hi","overlay":"nope"})", it, err) && it.overlay == 0);
  CHECK(parseItem(R"({"type":"animation","animation":"sprite_run","params":{"sprite":"rocket"}})", it, err));
  doc.clear();
  itemToJson(it, doc.to<JsonObject>());
  CHECK(strcmp(doc["params"]["sprite"] | "", "rocket") == 0);
}

static void testSettings() {
  std::puts("settings");
  Settings s;
  const char* err = nullptr;
  JsonDocument doc;

  deserializeJson(doc, R"({"brightness":9,"clock":{"format_24h":false,"date_every":30},
                          "night":{"enabled":true,"from":"22:30","to":"06:15","brightness":0}})");
  CHECK(settingsUpdate(s, doc.as<JsonObjectConst>(), err));
  CHECK(s.brightness == 9 && !s.clock.format24h && s.clock.dateEvery == 30);
  CHECK(s.night.enabled && s.night.from == 22 * 60 + 30 && s.night.to == 6 * 60 + 15);

  deserializeJson(doc, R"({"brightness":4.0,"night":{"brightness":2.0}})");
  CHECK(settingsUpdate(s, doc.as<JsonObjectConst>(), err));
  CHECK(s.brightness == 4 && s.night.brightness == 2);
  deserializeJson(doc, R"({"brightness":9})");
  settingsUpdate(s, doc.as<JsonObjectConst>(), err);

  // A bad value rejects the whole update and leaves settings untouched.
  deserializeJson(doc, R"({"brightness":3,"night":{"from":"25:00"}})");
  CHECK(!settingsUpdate(s, doc.as<JsonObjectConst>(), err));
  CHECK(s.brightness == 9);

  deserializeJson(doc, R"({"hostname":"bad name!"})");
  CHECK(!settingsUpdate(s, doc.as<JsonObjectConst>(), err));
  deserializeJson(doc, R"({"hostname":"dotmatrix-kitchen"})");
  CHECK(settingsUpdate(s, doc.as<JsonObjectConst>(), err));

  // Round trip (this is also what Storage writes to flash).
  JsonDocument out;
  settingsToJson(s, out.to<JsonObject>());
  Settings back;
  CHECK(settingsUpdate(back, out.as<JsonObjectConst>(), err));
  CHECK(back.night.from == s.night.from && strcmp(back.hostname, "dotmatrix-kitchen") == 0);
  CHECK(strcmp(out["night"]["to"] | "", "06:15") == 0);
}

// Run an animation item for its full duration; returns the last frame.
static Frame runAnimation(const char* json, uint32_t startMillis, int printEvery) {
  Item it;
  const char* err = nullptr;
  parseItem(json, it, err);
  Display display;
  Animation* a = animationAt(it.animation);
  Frame f;
  g_fakeMillis = startMillis;
  a->begin(it, display);
  uint32_t frameMs = it.frameMs ? it.frameMs : a->defaultFrameMs();
  int n = 0;
  for (uint32_t t = 0; t < it.duration; t += frameMs, n++) {
    g_fakeMillis = startMillis + t;
    a->step(f, g_fakeMillis);
    if (showFrames && printEvery && n % printEvery == 0) {
      std::printf("t=%5u ms\n", (unsigned)t);
      printFrame(f);
    }
  }
  return f;
}

static void testAnimations() {
  std::puts("animations");
  Display display;

  // matrix_reveal ends with exactly the text on screen.
  Item it;
  strlcpy(it.text, "MATRIX", sizeof(it.text));
  Frame expected;
  display.drawText(expected, it.text, Align::Center);
  std::srand(1);
  Frame last = runAnimation(R"({"type":"animation","animation":"matrix_reveal","duration":9000,"text":"MATRIX"})",
                            0, 25);
  CHECK(memcmp(last.col, expected.col, sizeof(last.col)) == 0);

  // Same result when millis() wraps around 2^32 mid-animation (49.7-day overflow).
  std::srand(1);
  Frame wrapped = runAnimation(R"({"type":"animation","animation":"matrix_reveal","duration":9000,"text":"MATRIX"})",
                               0xFFFFFFFFu - 4000, 0);
  CHECK(memcmp(wrapped.col, expected.col, sizeof(wrapped.col)) == 0);

  // matrix_rain keeps raining: frames are never empty after the start.
  std::srand(2);
  Frame rain = runAnimation(R"({"type":"animation","animation":"matrix_rain","duration":4000})", 0, 30);
  int lit = 0;
  for (int x = 0; x < DISPLAY_WIDTH; x++)
    for (int y = 0; y < DISPLAY_HEIGHT; y++) lit += rain.get(x, y);
  CHECK(lit > 5);

  // Custom narrow digits are used for the clock.
  Frame clk;
  uint16_t w = display.drawText(clk, "12:17:01", Align::Center);
  CHECK(w > 0 && w <= DISPLAY_WIDTH);
  if (showFrames) {
    std::puts("clock 12:17:01");
    printFrame(clk);
  }
}

static void testTime() {
  std::puts("stopwatch/timer");
  char b[16];
  formatStopwatch(0, b, sizeof(b));
  CHECK(strcmp(b, "00:00.00") == 0);
  formatStopwatch(83123, b, sizeof(b));
  CHECK(strcmp(b, "01:23.12") == 0);
  formatStopwatch(3723000, b, sizeof(b));
  CHECK(strcmp(b, "1:02:03") == 0);
  formatTimer(300000, b, sizeof(b));
  CHECK(strcmp(b, "05:00") == 0);
  formatTimer(1, b, sizeof(b));  // rounds up: never shows 00:00 before the end
  CHECK(strcmp(b, "00:01") == 0);
  formatTimer(0, b, sizeof(b));
  CHECK(strcmp(b, "00:00") == 0);
  formatTimer(3600000, b, sizeof(b));
  CHECK(strcmp(b, "1:00:00") == 0);

  // RunClock across the 49.7-day millis() wrap.
  RunClock c;
  uint32_t t0 = 0xFFFFFFFFu - 500;
  c.start(t0);
  CHECK(c.elapsed(t0 + 1500) == 1500);  // t0 + 1500 has wrapped past zero
  c.pause(t0 + 1500);
  CHECK(c.elapsed(t0 + 99999) == 1500);
  c.start(t0 + 2000);
  CHECK(c.elapsed(t0 + 2500) == 2000);
  c.reset();
  CHECK(c.elapsed(t0 + 3000) == 0 && !c.running);
}

static bool same(const Frame& a, const Frame& b) { return memcmp(a.col, b.col, sizeof(a.col)) == 0; }

static int lit(const Frame& f) {
  int n = 0;
  for (int x = 0; x < DISPLAY_WIDTH; x++)
    for (int y = 0; y < DISPLAY_HEIGHT; y++) n += f.get(x, y);
  return n;
}

static void testTextPosition() {
  std::puts("text position (same as Parola)");
  Display display;
  // Parola: right edge at (64 - w) / 2 columns from the right of the chain.
  for (const char* t : {"A", "AB", "Hello", "12:17:01", "W"}) {
    uint16_t w = display.textWidth(t);
    Frame f;
    display.drawText(f, t, Align::Center);
    int first = 0;
    while (first < DISPLAY_WIDTH && !f.col[first]) first++;
    // The glyph's first column may be empty, so compare against the layout start.
    int expected = DISPLAY_WIDTH - (int)w - (DISPLAY_WIDTH - (int)w) / 2;
    Frame g;
    display.drawText(g, t, Align::Left, expected);
    CHECK(same(f, g));
  }
  // UTF-8: "Ü" is C3 9C; 9C is an empty glyph, and Parola adds no gap after it.
  CHECK(display.textWidth("\xc3\x9c" "A") == display.textWidth("\xc3" "A"));
  // Wider than the display: starts at the left edge, like Parola.
  Frame a, b;
  display.drawText(a, "A long text that is wider than 64 columns", Align::Center);
  display.drawText(b, "A long text that is wider than 64 columns", Align::Left);
  CHECK(same(a, b));
}

static void testLasers() {
  std::puts("laser effects");
  Display display;
  Frame text;
  display.drawText(text, "LASER", Align::Center);
  for (FxKind k : {FxKind::LaserWrite, FxKind::LaserScan, FxKind::LaserCut, FxKind::LaserBeam}) {
    static TextFx fx;  // big (1 KB of pixel order), like the one in TextMode
    Frame f;
    // In: ends with exactly the text, in a bounded number of steps.
    fx.begin(text, k, true);
    int n = 0;
    while (fx.step(f) && n < 1000) {
      if (showFrames && n % 12 == 0) printFrame(f);
      n++;
    }
    CHECK(same(f, text));
    CHECK(n == fx.steps() && n > 10 && n <= 90);
    // Out: ends empty.
    fx.begin(text, k, false);
    n = 0;
    while (fx.step(f) && n < 1000) n++;
    CHECK(lit(f) == 0 && n == fx.steps());
  }
  // Laser cut visits every pixel of a long text, still in ~80 steps.
  Frame longText;
  display.drawText(longText, "WWWWWWWWWWW", Align::Left);
  static TextFx fx;
  fx.begin(longText, FxKind::LaserCut, true);
  CHECK(fx.steps() <= 80);
  Frame f;
  while (fx.step(f)) {}
  CHECK(same(f, longText));
  // An empty text finishes at once.
  fx.begin(Frame(), FxKind::LaserWrite, true);
  CHECK(!fx.step(f) && lit(f) == 0);
}

static void testOverlays() {
  std::puts("overlays");
  Display display;
  Frame text, f;
  display.drawText(text, "WAVE", Align::Center);
  Overlay o;
  // Wave: at the start the first letter is one row down, the rest unchanged.
  o.begin(text, OverlayKind::Wave, 8, 1000);
  CHECK(o.step(f, 1000) == 8);
  CHECK(!same(f, text) && lit(f) <= lit(text));
  // ... and after the wave has passed (resting), the text is as it was.
  o.step(f, 1000 + 4 * 110 + 100);
  CHECK(same(f, text));
  // Pulse: starts bright, dims to a quarter halfway, comes back.
  o.begin(text, OverlayKind::Pulse, 12, 0);
  CHECK(o.step(f, 0) == 12 && o.step(f, 800) == 3 && o.step(f, 1600) == 12);
  CHECK(same(f, text));
  // Border: the text is untouched, plus 6 dots on the edge.
  o.begin(Frame(), OverlayKind::Border, 8, 0);
  o.step(f, 5000);
  CHECK(lit(f) == 6);
  // Sparkle adds a few pixels.
  o.begin(text, OverlayKind::Sparkle, 8, 0);
  o.step(f, 100);
  CHECK(lit(f) >= lit(text) - 1);
  CHECK(overlayIndex("border") == 4 && overlayIndex(nullptr) == 0);
}

static void testScenes() {
  std::puts("animations: starfield, life, fireworks, equalizer, snake, sprite_run");
  for (const char* id : {"starfield", "life", "fireworks", "equalizer", "snake", "sprite_run"}) {
    char json[160];
    snprintf(json, sizeof(json), R"({"type":"animation","animation":"%s","duration":60000})", id);
    std::srand(7);
    // Run a minute of frames (catches crashes and endless loops), counting busy frames.
    Item it;
    const char* err = nullptr;
    CHECK(parseItem(json, it, err));
    Animation* a = animationAt(it.animation);
    CHECK(a != nullptr);
    if (!a) continue;
    Display display;
    a->begin(it, display);
    Frame f;
    int busy = 0, frames = 0;
    for (uint32_t t = 0; t < 60000; t += a->defaultFrameMs(), frames++) {
      g_fakeMillis = t;
      CHECK(a->step(f, t));
      busy += lit(f) > 0;
      if (showFrames && frames % 150 == 0) {
        std::printf("%s t=%u\n", id, (unsigned)t);
        printFrame(f);
      }
    }
    CHECK(busy > frames * 3 / 4);
  }
}

int main(int argc, char** argv) {
  showFrames = argc > 1 && strcmp(argv[1], "--show") == 0;
  testItems();
  testSettings();
  testAnimations();
  testTime();
  testTextPosition();
  testLasers();
  testOverlays();
  testScenes();
  std::printf(failures ? "\n%d FAILED\n" : "\nall tests passed\n", failures);
  return failures ? 1 : 0;
}
