#!/bin/sh
# Build and run the host tests. Needs a C++17 compiler and ArduinoJson.
#   ARDUINOJSON=/path/to/ArduinoJson/src ./test_host/run.sh [--show]
set -e
cd "$(dirname "$0")/.."
AJ="${ARDUINOJSON:-.pio/libdeps/esp32c3/ArduinoJson/src}"
OUT="${TMPDIR:-/tmp}/dotmatrix_host_tests"
c++ -std=c++17 -O1 -Wall -Wextra -Wno-unused-parameter \
  -I test_host/stubs -I "$AJ" \
  src/model/Item.cpp src/model/Settings.cpp \
  src/display/Effects.cpp src/display/Sprites.cpp src/display/DisplayText.cpp \
  src/animations/Registry.cpp src/animations/MatrixRain.cpp \
  test_host/host_display.cpp test_host/test_main.cpp \
  -o "$OUT"
"$OUT" "$@"
