#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

// HTTP + WebSocket server on port 80.
//   /ws          JSON protocol (see docs/DESIGN.md §6)
//   /            setup / status page
//   /api/scan    nearby Wi-Fi networks (JSON)
//   /api/wifi    POST ssid + password, then reboot
//   /update      POST firmware .bin (OTA)
//
// The server runs on the network task. Incoming WebSocket messages are queued
// and handled in loop(), so display and storage are only touched from one task.
namespace WebServer {

enum class EventKind : uint8_t { Connected, Disconnected, Message };

struct Event {
  EventKind kind;
  uint32_t client;
  char* data;  // Message only; free() after use
  size_t len;
};

void begin();
// Pop the next event; returns false if none.
bool poll(Event& ev);
void cleanup();  // call ~1×/s

void send(uint32_t client, const JsonDocument& doc);
void broadcast(const JsonDocument& doc);
size_t clientCount();

// Status shown on the setup page.
void setStatus(const String& json);
// Set when a firmware upload or Wi-Fi change needs a reboot.
bool rebootRequested();
bool otaInProgress();
}  // namespace WebServer
