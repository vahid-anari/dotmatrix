#pragma once
#include <stdint.h>

// How far a firmware upload has got, for the display (since 0.8.7). Both ways of
// updating report here: the app's upload (WebServer, in the network task; the
// main loop draws it) and PlatformIO's (ArduinoOTA, which holds up the main loop
// for the whole upload, so it calls `draw` itself).
namespace OtaProgress {
extern volatile int8_t percent;     // -1 when no upload is running
extern volatile bool failed;        // the last upload failed; the loop shows it and clears it
extern void (*draw)(int8_t percent);  // set by the app; for ArduinoOTA's blocking upload
}  // namespace OtaProgress
