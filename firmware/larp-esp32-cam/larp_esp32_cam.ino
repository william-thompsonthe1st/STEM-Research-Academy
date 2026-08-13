/* LARP reconnaissance-camera firmware for an Inland ESP32-CAM.
   Flash once with CAMERA_ID='A' and once with CAMERA_ID='B'. The pin map is
   for the common AI Thinker-compatible Inland ESP32-CAM; verify your board's
   printed pinout before powering it. */

#include <Arduino.h>
#include <ESPmDNS.h>
#include <WiFi.h>
#include "esp_camera.h"
#include "esp_http_server.h"

constexpr char CAMERA_ID = 'A';  // Change the second board to 'B'.
constexpr char WIFI_SSID[] = "3TSahur-Swarm";
// Copy HOTSPOT_PASSWORD from the Pi config.env before flashing. Never commit
// the real password; every ECHO and ESP32-CAM must receive the same value.
constexpr char WIFI_PASSWORD[] = "REPLACE_WITH_PI_PASSWORD";
constexpr unsigned long WIFI_RETRY_A_MS = 2000;
constexpr unsigned long WIFI_RETRY_B_MS = 2400;
constexpr unsigned long STREAM_FRAME_INTERVAL_MS = 100;  // 10 FPS maximum.
static_assert(CAMERA_ID == 'A' || CAMERA_ID == 'B', "CAMERA_ID must be A or B");

const char *cameraHost() { return CAMERA_ID == 'A' ? "larp-a-cam" : "larp-b-cam"; }
const char *cameraName() { return CAMERA_ID == 'A' ? "LARP Scout A Camera" : "LARP Scout B Camera"; }
unsigned long wifiRetryMs() { return CAMERA_ID == 'A' ? WIFI_RETRY_A_MS : WIFI_RETRY_B_MS; }

// AI Thinker-compatible ESP32-CAM pin assignment.
constexpr int PWDN = 32, RESET = -1, XCLK = 0, SIOD = 26, SIOC = 27;
constexpr int Y9 = 35, Y8 = 34, Y7 = 39, Y6 = 36, Y5 = 21, Y4 = 19, Y3 = 18, Y2 = 5;
constexpr int VSYNC = 25, HREF = 23, PCLK = 22;
httpd_handle_t server = nullptr;
bool mdnsStarted = false;
bool wifiWasConnected = false;
bool serverStarted = false;
unsigned long lastWiFiAttemptAt = 0;

esp_err_t statusHandler(httpd_req_t *request) {
  const String body = String("{\"ok\":true,\"id\":\"") + CAMERA_ID +
      "\",\"name\":\"" + cameraName() + "\",\"ip\":\"" + WiFi.localIP().toString() + "\"}";
  httpd_resp_set_type(request, "application/json");
  return httpd_resp_send(request, body.c_str(), body.length());
}

esp_err_t homeHandler(httpd_req_t *request) {
  const String body = String("<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'><title>") +
      cameraName() + "</title><style>body{margin:2rem;background:#071316;color:#effafa;font-family:system-ui}img{max-width:100%}</style><h1>" +
      cameraName() + "</h1><img src=/stream alt='Live camera feed'>";
  httpd_resp_set_type(request, "text/html");
  return httpd_resp_send(request, body.c_str(), body.length());
}

esp_err_t streamHandler(httpd_req_t *request) {
  httpd_resp_set_type(request, "multipart/x-mixed-replace;boundary=frame");
  httpd_resp_set_hdr(request, "Access-Control-Allow-Origin", "*");
  while (true) {
    const unsigned long frameStartedAt = millis();
    camera_fb_t *frame = esp_camera_fb_get();
    if (frame == nullptr) return ESP_FAIL;
    char header[96];
    const int length = snprintf(header, sizeof(header), "\r\n--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", frame->len);
    esp_err_t result = httpd_resp_send_chunk(request, header, length);
    if (result == ESP_OK) result = httpd_resp_send_chunk(request, reinterpret_cast<const char *>(frame->buf), frame->len);
    esp_camera_fb_return(frame);
    if (result != ESP_OK) return result;  // Client disconnected.
    // ESP32-CAMs can otherwise emit VGA frames as fast as possible and flood
    // the shared 2.4 GHz control network. Keep capacity for drive commands.
    const unsigned long elapsed = millis() - frameStartedAt;
    if (elapsed < STREAM_FRAME_INTERVAL_MS) vTaskDelay(pdMS_TO_TICKS(STREAM_FRAME_INTERVAL_MS - elapsed));
  }
}

bool startCamera() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0; config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2; config.pin_d1 = Y3; config.pin_d2 = Y4; config.pin_d3 = Y5;
  config.pin_d4 = Y6; config.pin_d5 = Y7; config.pin_d6 = Y8; config.pin_d7 = Y9;
  config.pin_xclk = XCLK; config.pin_pclk = PCLK; config.pin_vsync = VSYNC; config.pin_href = HREF;
  config.pin_sccb_sda = SIOD; config.pin_sccb_scl = SIOC; config.pin_pwdn = PWDN; config.pin_reset = RESET;
  config.xclk_freq_hz = 20000000; config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA; config.jpeg_quality = psramFound() ? 12 : 16;
  config.fb_count = psramFound() ? 2 : 1; config.grab_mode = CAMERA_GRAB_LATEST;
  return esp_camera_init(&config) == ESP_OK;
}

bool startServer() {
  // The HTTP server survives a Wi-Fi reconnect. Starting a second instance
  // can fail after a transient hotspot outage, so reuse the original server.
  if (server != nullptr) return true;
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.lru_purge_enable = true;
  if (httpd_start(&server, &config) != ESP_OK) return false;
  httpd_uri_t root = {.uri="/", .method=HTTP_GET, .handler=homeHandler, .user_ctx=nullptr};
  httpd_uri_t status = {.uri="/status", .method=HTTP_GET, .handler=statusHandler, .user_ctx=nullptr};
  httpd_uri_t stream = {.uri="/stream", .method=HTTP_GET, .handler=streamHandler, .user_ctx=nullptr};
  httpd_register_uri_handler(server, &root); httpd_register_uri_handler(server, &status); httpd_register_uri_handler(server, &stream);
  return true;
}

void beginWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false);
  WiFi.setHostname(cameraHost());
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lastWiFiAttemptAt = millis();
  Serial.printf("%s joining %s in station mode...\n", cameraName(), WIFI_SSID);
}

void maintainWiFi() {
  const bool connected = WiFi.status() == WL_CONNECTED;
  if (connected) {
    if (!wifiWasConnected) {
      wifiWasConnected = true;
      mdnsStarted = MDNS.begin(cameraHost());
      if (mdnsStarted) MDNS.addService("http", "tcp", 80);
      serverStarted = startServer();
      if (!serverStarted) Serial.println("Camera HTTP server failed to start; reconnect Wi-Fi to retry.");
      Serial.printf("%s ready: http://%s.local/stream\n", cameraName(), cameraHost());
    }
    return;
  }

  if (wifiWasConnected) {
    wifiWasConnected = false;
    if (mdnsStarted) MDNS.end();
    mdnsStarted = false;
    Serial.println("Camera Wi-Fi disconnected; retrying the Pi hotspot.");
  }
  if (millis() - lastWiFiAttemptAt < wifiRetryMs()) return;
  lastWiFiAttemptAt = millis();
  // Never block setup waiting for the hotspot: cameras may boot before 3TSahur.
  WiFi.disconnect(false, false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void setup() {
  Serial.begin(115200);
  if (!startCamera()) { Serial.println("Camera initialization failed; check the board pin map and power."); return; }
  beginWiFi();
}

void loop() { maintainWiFi(); delay(20); }
