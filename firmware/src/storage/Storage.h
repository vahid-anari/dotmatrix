#pragma once
#include <vector>

#include "../model/Item.h"
#include "../model/Settings.h"

// Persists the playlist and settings to LittleFS, and Wi-Fi credentials to NVS.
// Files are written to a temp file and renamed, so a power cut mid-write never
// leaves a half-written playlist.
namespace Storage {
bool begin();

bool loadSettings(Settings& s);
bool saveSettings(const Settings& s);

bool loadPlaylist(std::vector<Item>& items, char* name, size_t nameLen);
bool savePlaylist(const std::vector<Item>& items, const char* name);

bool loadWifi(String& ssid, String& password);
void saveWifi(const char* ssid, const char* password);
void clearWifi();
}  // namespace Storage
