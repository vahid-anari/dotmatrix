#include "Registry.h"

#include "MatrixRain.h"
#include "Scenes.h"

// ---- Add new animations here (at the end, so indexes stay put) -------------
static MatrixRain matrixRain(false);
static MatrixRain matrixReveal(true);
static Starfield starfield;
static Life life;
static Fireworks fireworks;
static Equalizer equalizer;
static Snake snake;
static SpriteRun spriteRun;

static const struct {
  const char* id;
  Animation* anim;
} ANIMATIONS[] = {
    {"matrix_rain", &matrixRain},
    {"matrix_reveal", &matrixReveal},
    {"starfield", &starfield},
    {"life", &life},
    {"fireworks", &fireworks},
    {"equalizer", &equalizer},
    {"snake", &snake},
    {"sprite_run", &spriteRun},
};
// ---------------------------------------------------------------------------

static constexpr uint8_t COUNT = sizeof(ANIMATIONS) / sizeof(ANIMATIONS[0]);

int animationIndex(const char* id) {
  if (!id) return -1;
  for (uint8_t i = 0; i < COUNT; i++)
    if (strcmp(ANIMATIONS[i].id, id) == 0) return i;
  return -1;
}

const char* animationId(uint8_t index) { return index < COUNT ? ANIMATIONS[index].id : ""; }
uint8_t animationCount() { return COUNT; }
Animation* animationAt(uint8_t index) { return index < COUNT ? ANIMATIONS[index].anim : nullptr; }
