#include "Registry.h"

#include "MatrixRain.h"

// ---- Add new animations here ----------------------------------------------
static MatrixRain matrixRain(false);
static MatrixRain matrixReveal(true);

static const struct {
  const char* id;
  Animation* anim;
} ANIMATIONS[] = {
    {"matrix_rain", &matrixRain},
    {"matrix_reveal", &matrixReveal},
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
