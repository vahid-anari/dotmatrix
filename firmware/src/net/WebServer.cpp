#include "WebServer.h"

#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>
#include <Update.h>
#include <WiFi.h>

#include "../config.h"
#include "../storage/Storage.h"
#include "SetupPage.h"

using WebServer::EventKind;

static AsyncWebServer server(80);
static AsyncWebSocket ws("/ws");
static QueueHandle_t events;

static volatile bool rebootFlag = false;
static volatile bool otaFlag = false;
static String status = "{}";
static SemaphoreHandle_t statusLock;

// Per-client buffer for messages that arrive in several TCP chunks.
struct Partial {
  char* buf = nullptr;
  size_t len = 0;
};

static void pushEvent(EventKind kind, uint32_t client, char* data = nullptr, size_t len = 0) {
  WebServer::Event ev{kind, client, data, len};
  if (xQueueSend(events, &ev, 0) != pdTRUE) {
    free(data);
    LOG("ws: event queue full, dropped");
  }
}

static void onWsEvent(AsyncWebSocket* s, AsyncWebSocketClient* c, AwsEventType type, void* arg,
                      uint8_t* data, size_t len) {
  switch (type) {
    case WS_EVT_CONNECT:
      if (s->count() > MAX_WS_CLIENTS) {
        c->close(1013, "too many clients");
        return;
      }
      c->_tempObject = new Partial();
      pushEvent(EventKind::Connected, c->id());
      break;

    case WS_EVT_DISCONNECT: {
      Partial* p = (Partial*)c->_tempObject;
      if (p) {
        free(p->buf);
        delete p;
        c->_tempObject = nullptr;
      }
      pushEvent(EventKind::Disconnected, c->id());
      break;
    }

    case WS_EVT_DATA: {
      AwsFrameInfo* info = (AwsFrameInfo*)arg;
      Partial* p = (Partial*)c->_tempObject;
      if (!p || info->opcode != WS_TEXT || info->num != 0 || !info->final) return;  // text, single frame
      if (info->len > MAX_WS_MESSAGE) {
        if (info->index == 0) c->text("{\"evt\":\"error\",\"error\":\"message too large\"}");
        return;
      }
      if (info->index == 0) {
        free(p->buf);
        p->buf = (char*)malloc(info->len + 1);
        p->len = 0;
        if (!p->buf) return;
      }
      if (!p->buf || info->index + len > info->len) return;
      memcpy(p->buf + info->index, data, len);
      p->len = info->index + len;
      if (p->len == info->len) {
        p->buf[p->len] = '\0';
        pushEvent(EventKind::Message, c->id(), p->buf, p->len);
        p->buf = nullptr;  // ownership moved to the queue
        p->len = 0;
      }
      break;
    }

    default:
      break;
  }
}

// ------------------------------------------------------------------ HTTP

static bool isCaptiveRequest(AsyncWebServerRequest* r) {
  // In setup mode, any host other than our own IP is a phone probing for a portal.
  if (!(WiFi.getMode() & WIFI_AP)) return false;
  String host = r->host();
  return host != WiFi.softAPIP().toString() && !host.endsWith(".local");
}

static void handleScan(AsyncWebServerRequest* r) {
  int n = WiFi.scanComplete();
  if (n == WIFI_SCAN_FAILED) {
    WiFi.scanNetworks(true);  // async; the page polls again
    r->send(202, "application/json", "{\"scanning\":true}");
    return;
  }
  if (n == WIFI_SCAN_RUNNING) {
    r->send(202, "application/json", "{\"scanning\":true}");
    return;
  }
  JsonDocument doc;
  JsonArray arr = doc["networks"].to<JsonArray>();
  for (int i = 0; i < n && i < 20; i++) {
    if (WiFi.SSID(i).isEmpty()) continue;
    JsonObject o = arr.add<JsonObject>();
    o["ssid"] = WiFi.SSID(i);
    o["rssi"] = WiFi.RSSI(i);
    o["open"] = WiFi.encryptionType(i) == WIFI_AUTH_OPEN;
  }
  WiFi.scanDelete();
  String out;
  serializeJson(doc, out);
  r->send(200, "application/json", out);
}

static void handleWifi(AsyncWebServerRequest* r) {
  if (!r->hasParam("ssid", true)) {
    r->send(400, "text/plain", "missing ssid");
    return;
  }
  String ssid = r->getParam("ssid", true)->value();
  String pass = r->hasParam("password", true) ? r->getParam("password", true)->value() : "";
  if (ssid.isEmpty() || ssid.length() > 32 || pass.length() > 64) {
    r->send(400, "text/plain", "invalid ssid or password");
    return;
  }
  Storage::saveWifi(ssid.c_str(), pass.c_str());
  LOG("wifi: saved '%s' from setup page, rebooting", ssid.c_str());
  r->send(200, "application/json", "{\"ok\":true}");
  rebootFlag = true;
}

static size_t otaBytes = 0;

static void otaAbort(const char* why) {
  if (Update.isRunning()) Update.abort();
  if (otaFlag) LOG("ota: aborted (%s)", why);
  otaFlag = false;
  otaBytes = 0;
}

static void handleUpdateUpload(AsyncWebServerRequest* r, const String& filename, size_t index,
                               uint8_t* data, size_t len, bool final) {
  if (index == 0) {
    otaAbort("new upload");  // clears a previous upload that never finished
    LOG("ota: receiving %s", filename.c_str());
    if (!Update.begin(UPDATE_SIZE_UNKNOWN, U_FLASH)) {
      LOG("ota: begin failed: %s", Update.errorString());
      return;
    }
    otaFlag = true;
    // If the phone drops the connection mid-upload, don't stay stuck.
    r->onDisconnect([]() {
      if (otaFlag && !rebootFlag) otaAbort("client disconnected");
    });
  }
  if (!Update.isRunning()) return;
  if (Update.write(data, len) != len) {
    LOG("ota: write failed: %s", Update.errorString());
    otaAbort("write failed");
    return;
  }
  otaBytes += len;
  if (final) {
    bool ok = Update.end(true);
    LOG("ota: %s (%u bytes)", ok ? "done" : Update.errorString(), (unsigned)otaBytes);
    if (!ok) otaAbort("verify failed");
  }
}

static void handleUpdateDone(AsyncWebServerRequest* r) {
  // Success only if a file actually arrived and verified.
  bool ok = otaBytes > 0 && Update.isFinished() && !Update.hasError();
  r->send(ok ? 200 : 500, "application/json", ok ? "{\"ok\":true}" : "{\"ok\":false}");
  if (ok)
    rebootFlag = true;
  else
    otaAbort("no valid file");
  otaFlag = false;
}

void WebServer::begin() {
  events = xQueueCreate(16, sizeof(Event));
  statusLock = xSemaphoreCreateMutex();

  ws.onEvent(onWsEvent);
  server.addHandler(&ws);

  server.on("/", HTTP_GET, [](AsyncWebServerRequest* r) {
    r->send(200, "text/html", SETUP_PAGE);
  });
  server.on("/api/status", HTTP_GET, [](AsyncWebServerRequest* r) {
    xSemaphoreTake(statusLock, portMAX_DELAY);
    String s = status;
    xSemaphoreGive(statusLock);
    r->send(200, "application/json", s);
  });
  server.on("/api/scan", HTTP_GET, handleScan);
  server.on("/api/wifi", HTTP_POST, handleWifi);
  server.on("/update", HTTP_POST, handleUpdateDone, handleUpdateUpload);

  server.onNotFound([](AsyncWebServerRequest* r) {
    if (isCaptiveRequest(r))
      r->redirect("http://" + WiFi.softAPIP().toString() + "/");
    else
      r->send(404, "text/plain", "not found");
  });

  server.begin();
  LOG("http: server started on port 80");
}

bool WebServer::poll(Event& ev) { return xQueueReceive(events, &ev, 0) == pdTRUE; }

void WebServer::cleanup() { ws.cleanupClients(MAX_WS_CLIENTS); }

// Serialize straight into one shared buffer: no String growth, no extra copy.
static AsyncWebSocketSharedBuffer toBuffer(const JsonDocument& doc) {
  size_t n = measureJson(doc);
  auto buf = std::make_shared<std::vector<uint8_t>>(n + 1);
  if (!buf || buf->size() != n + 1) return nullptr;
  serializeJson(doc, (char*)buf->data(), n + 1);
  buf->resize(n);  // drop the terminator
  return buf;
}

void WebServer::send(uint32_t client, const JsonDocument& doc) {
  auto buf = toBuffer(doc);
  if (buf)
    ws.text(client, buf);
  else
    LOG("ws: out of memory sending %u bytes", (unsigned)measureJson(doc));
}

void WebServer::broadcast(const JsonDocument& doc) {
  if (ws.count() == 0) return;
  auto buf = toBuffer(doc);
  if (buf) ws.textAll(buf);
}

size_t WebServer::clientCount() { return ws.count(); }

void WebServer::setStatus(const String& json) {
  xSemaphoreTake(statusLock, portMAX_DELAY);
  status = json;
  xSemaphoreGive(statusLock);
}

bool WebServer::rebootRequested() { return rebootFlag; }
bool WebServer::otaInProgress() { return otaFlag; }
