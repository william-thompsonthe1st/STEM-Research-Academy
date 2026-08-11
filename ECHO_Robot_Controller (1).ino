/*
  ECHO Robot Controller
  =====================
  Shared firmware for both identical ECHO-board differential-drive scouts.

  Before flashing, change ROBOT_ID to 'A' or 'B'. Everything else stays the
  same. The robot joins the Raspberry Pi hotspot in station mode, serves a
  small standalone control page, exposes endpoints used by the Pi dashboard,
  and reports a coarse Wi-Fi CSI disturbance signal.

  Hardware target: ECHO board / ESP32-S3
  Arduino board: ESP32S3 Dev Module
  Libraries: EchoLib and its documented dependencies

  IMPORTANT: Motor direction has not been physically verified. Test with the
  wheels lifted, a low speed, and immediate access to motor power.
*/

#include <Arduino.h>
#include <EchoLib.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include "esp_wifi.h"

// ---------------------------------------------------------------------------
// Robot configuration
// ---------------------------------------------------------------------------

constexpr char ROBOT_ID = 'A';  // Flash one board as 'A' and the other as 'B'.

constexpr char WIFI_SSID[] = "EchoSwarm";
constexpr char WIFI_PASSWORD[] = "roboswarm1";

constexpr uint8_t LEFT_MOTOR_ID = 1;
constexpr uint8_t RIGHT_MOTOR_ID = 6;
constexpr uint8_t STARTUP_SPEED_LIMIT = 35;
constexpr unsigned long COMMAND_TIMEOUT_MS = 500;
constexpr unsigned long WIFI_RETRY_MS = 5000;

constexpr uint16_t PI_CSI_UDP_PORT = 5005;
constexpr uint16_t PI_HEARTBEAT_UDP_PORT = 5006;
constexpr unsigned long HEARTBEAT_INTERVAL_MS = 1000;
constexpr unsigned long CSI_REPORT_INTERVAL_MS = 250;
constexpr uint16_t PI_DASHBOARD_PORT = 8080;
constexpr unsigned long PI_REGISTRATION_INTERVAL_MS = 4000;
const IPAddress PI_ADDRESS(10, 42, 0, 1);

static_assert(ROBOT_ID == 'A' || ROBOT_ID == 'B', "ROBOT_ID must be A or B");

const char *robotName() { return ROBOT_ID == 'A' ? "ECHO Scout A" : "ECHO Scout B"; }
const char *robotHost() { return ROBOT_ID == 'A' ? "echo-scout-a" : "echo-scout-b"; }
const char *cameraHost() { return ROBOT_ID == 'A' ? "echo-scout-a-cam.local" : "echo-scout-b-cam.local"; }

// EchoLib's documented differential-drive class accepts turn (X) and
// forward/reverse (Y) values. Motors 1 and 6 match the Zippy example.
MotorControllers motors;
TankDrive drivetrain(motors, LEFT_MOTOR_ID, RIGHT_MOTOR_ID);
WebServer server(80);
WiFiUDP csiUdp;

unsigned long lastCommandAt = 0;
unsigned long lastWiFiAttemptAt = 0;
unsigned long lastHeartbeatAt = 0;
unsigned long lastCsiReportAt = 0;
bool motorsStopped = true;
bool mdnsStarted = false;
bool heartbeatAnnounced = false;
volatile bool piRegistered = false;
volatile unsigned long lastPiRegistrationAt = 0;

// ---------------------------------------------------------------------------
// CSI disturbance sensing
// ---------------------------------------------------------------------------
// This is a coarse motion/presence signal. It is not a camera, a direction
// finder, person identification, distance measurement, or localization.

constexpr size_t CSI_WINDOW_SIZE = 40;
constexpr float CSI_VARIANCE_THRESHOLD = 6.0f;
constexpr unsigned long CSI_HOLD_MS = 1500;

float csiWindow[CSI_WINDOW_SIZE] = {};
size_t csiWindowIndex = 0;
size_t csiWindowCount = 0;
float csiMotionLevel = 0;
bool csiMotionDetected = false;
unsigned long lastCsiMotionAt = 0;

volatile bool csiReady = false;
volatile float csiLatestEnergy = 0;
volatile uint32_t csiPacketCount = 0;
portMUX_TYPE csiMux = portMUX_INITIALIZER_UNLOCKED;

void onCsiReceived(void *, wifi_csi_info_t *info) {
  if (info == nullptr || info->buf == nullptr || info->len < 2) return;

  int64_t sumSquares = 0;
  const size_t pairs = info->len / 2;
  for (size_t i = 0; i < pairs; ++i) {
    const int8_t imaginary = info->buf[i * 2];
    const int8_t real = info->buf[i * 2 + 1];
    sumSquares += static_cast<int32_t>(imaginary) * imaginary;
    sumSquares += static_cast<int32_t>(real) * real;
  }
  const float energy = sqrtf(static_cast<float>(sumSquares) / pairs);

  portENTER_CRITICAL_ISR(&csiMux);
  csiLatestEnergy = energy;
  ++csiPacketCount;
  csiReady = true;
  portEXIT_CRITICAL_ISR(&csiMux);
}

void startCsi() {
  wifi_csi_config_t config = {};
  config.lltf_en = true;
  config.htltf_en = true;
  config.stbc_htltf2_en = true;
  config.ltf_merge_en = true;
  config.channel_filter_en = false;
  config.manu_scale = false;
  config.shift = false;

  wifi_promiscuous_filter_t filter = {};
  filter.filter_mask = WIFI_PROMIS_FILTER_MASK_DATA | WIFI_PROMIS_FILTER_MASK_MGMT;

  esp_err_t result = esp_wifi_set_promiscuous(true);
  if (result == ESP_OK) result = esp_wifi_set_promiscuous_filter(&filter);
  if (result == ESP_OK) result = esp_wifi_set_csi_config(&config);
  if (result == ESP_OK) result = esp_wifi_set_csi_rx_cb(&onCsiReceived, nullptr);
  if (result == ESP_OK) result = esp_wifi_set_csi(true);

  Serial.printf("CSI startup: %s (0x%x)\n", result == ESP_OK ? "enabled" : "unavailable", result);
}

void processCsi() {
  float energy = 0;
  uint32_t packets = 0;

  portENTER_CRITICAL(&csiMux);
  if (!csiReady) {
    portEXIT_CRITICAL(&csiMux);
    return;
  }
  csiReady = false;
  energy = csiLatestEnergy;
  packets = csiPacketCount;
  portEXIT_CRITICAL(&csiMux);

  csiWindow[csiWindowIndex] = energy;
  csiWindowIndex = (csiWindowIndex + 1) % CSI_WINDOW_SIZE;
  if (csiWindowCount < CSI_WINDOW_SIZE) ++csiWindowCount;

  if (csiWindowCount >= 5) {
    float mean = 0;
    for (size_t i = 0; i < csiWindowCount; ++i) mean += csiWindow[i];
    mean /= csiWindowCount;

    float variance = 0;
    for (size_t i = 0; i < csiWindowCount; ++i) {
      const float difference = csiWindow[i] - mean;
      variance += difference * difference;
    }
    variance /= csiWindowCount;
    csiMotionLevel = constrain(variance, 0.0f, 100.0f);

    if (variance >= CSI_VARIANCE_THRESHOLD) {
      csiMotionDetected = true;
      lastCsiMotionAt = millis();
    } else if (millis() - lastCsiMotionAt > CSI_HOLD_MS) {
      csiMotionDetected = false;
    }
  }

  // A compact summary is mirrored to the Pi at a fixed low rate. Sending one
  // datagram per received Wi-Fi packet would flood the control link.
  if (millis() - lastCsiReportAt < CSI_REPORT_INTERVAL_MS) return;
  lastCsiReportAt = millis();
  struct __attribute__((packed)) CsiSummary {
    char robotId;
    uint32_t packetCount;
    uint32_t timestampMs;
    float energy;
    float motionLevel;
  } summary = {ROBOT_ID, packets, millis(), energy, csiMotionLevel};

  csiUdp.beginPacket(PI_ADDRESS, PI_CSI_UDP_PORT);
  csiUdp.write(reinterpret_cast<const uint8_t *>(&summary), sizeof(summary));
  csiUdp.endPacket();
}

void sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED || millis() - lastHeartbeatAt < HEARTBEAT_INTERVAL_MS) return;
  lastHeartbeatAt = millis();
  String heartbeat = "{\"id\":\"" + String(ROBOT_ID) + "\",\"rssi\":";
  heartbeat += String(WiFi.RSSI());
  heartbeat += ",\"uptime_ms\":" + String(millis()) + "}";
  csiUdp.beginPacket(PI_ADDRESS, PI_HEARTBEAT_UDP_PORT);
  csiUdp.print(heartbeat);
  const bool sent = csiUdp.endPacket() == 1;
  if (sent && !heartbeatAnnounced) {
    heartbeatAnnounced = true;
    Serial.println("UDP heartbeat sent to Pi on port 5006.");
  }
}

// Register over TCP as well as UDP. This gives the Pi the Scout's DHCP
// address even on networks where multicast DNS or UDP discovery is filtered.
// It runs in a background FreeRTOS task, so a slow registration attempt can
// never block server.handleClient() or the motor watchdog.
bool registerWithPi() {
  if (WiFi.status() != WL_CONNECTED) return false;

  WiFiClient client;
  client.setTimeout(300);
  if (!client.connect(PI_ADDRESS, PI_DASHBOARD_PORT)) return false;

  String path = "/api/scouts/register?id=";
  path += ROBOT_ID;
  path += "&rssi=" + String(WiFi.RSSI());
  path += "&uptime_ms=" + String(millis());
  client.print("GET ");
  client.print(path);
  client.print(" HTTP/1.1\r\n");
  client.print("Host: 10.42.0.1:8080\r\n");
  client.print("Connection: close\r\n\r\n");

  const unsigned long responseStartedAt = millis();
  while (!client.available() && client.connected() && millis() - responseStartedAt < 500) {
    vTaskDelay(pdMS_TO_TICKS(10));
  }
  const String statusLine = client.available() ? client.readStringUntil('\n') : "";
  const bool accepted = statusLine.indexOf(" 200 ") >= 0;
  client.stop();
  if (accepted) lastPiRegistrationAt = millis();
  return accepted;
}

void piRegistrationTask(void *) {
  vTaskDelay(pdMS_TO_TICKS(750));
  bool firstAttempt = true;
  for (;;) {
    const bool wasRegistered = piRegistered;
    const bool registered = registerWithPi();
    if (registered) {
      piRegistered = true;
    } else if (lastPiRegistrationAt == 0 || millis() - lastPiRegistrationAt > PI_REGISTRATION_INTERVAL_MS * 3) {
      piRegistered = false;
    }
    if (piRegistered != wasRegistered || (firstAttempt && !piRegistered)) {
      Serial.printf("Pi registration: %s\n", piRegistered ? "HTTP 200 - dashboard connected" : "connection lost; retrying");
    }
    firstAttempt = false;
    vTaskDelay(pdMS_TO_TICKS(PI_REGISTRATION_INTERVAL_MS));
  }
}

// ---------------------------------------------------------------------------
// Motor safety and HTTP API
// ---------------------------------------------------------------------------

void stopMotors() {
  drivetrain.drive(0, 0);
  motorsStopped = true;
}

void sendJson(const String &body, int status = 200) {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Cache-Control", "no-store");
  server.send(status, "application/json", body);
}

void handleDrive() {
  int x = constrain(server.arg("x").toInt(), -100, 100);
  int y = constrain(server.arg("y").toInt(), -100, 100);
  int speed = server.hasArg("speed") ? constrain(server.arg("speed").toInt(), 0, 100) : STARTUP_SPEED_LIMIT;

  x = (x * speed) / 100;
  y = (y * speed) / 100;
  drivetrain.drive(x, y);
  motorsStopped = x == 0 && y == 0;
  lastCommandAt = millis();
  sendJson("{\"ok\":true}");
}

void handleStop() {
  stopMotors();
  lastCommandAt = millis();
  sendJson("{\"ok\":true,\"stopped\":true}");
}

void handleStatus() {
  String json = "{";
  json += "\"id\":\"" + String(ROBOT_ID) + "\",";
  json += "\"name\":\"" + String(robotName()) + "\",";
  json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"rssi\":" + String(WiFi.RSSI()) + ",";
  json += "\"stopped\":" + String(motorsStopped ? "true" : "false") + ",";
  json += "\"motion\":" + String(csiMotionDetected ? "true" : "false") + ",";
  json += "\"motion_level\":" + String(csiMotionLevel, 1) + ",";
  json += "\"csi_packets\":" + String(csiPacketCount) + ",";
  json += "\"pi_registered\":" + String(piRegistered ? "true" : "false") + ",";
  json += "\"uptime_ms\":" + String(millis());
  json += "}";
  sendJson(json);
}

const char CONTROL_PAGE[] PROGMEM = R"HTML(
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>ECHO Scout</title><style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#08100f;color:#f2f7f5;font-family:system-ui,sans-serif}
main{width:min(440px,94vw);padding:24px;border:1px solid #29403b;border-radius:18px;background:#101a18}h1{margin:0 0 4px}.muted{color:#8da39d}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:24px 0}.grid button{min-height:70px;border:1px solid #3e5b54;border-radius:12px;background:#172622;color:white;font-size:20px;font-weight:800;touch-action:none}.grid button:active,.stop{background:#b9ff38!important;color:#08100f!important}.blank{visibility:hidden}.stop{border-color:#b9ff38!important}.bar{height:8px;border-radius:8px;background:#23332f;overflow:hidden}.bar i{display:block;height:100%;width:0;background:#45e5ff}.row{display:flex;justify-content:space-between;margin:12px 0}
</style></head><body><main><p class="muted">EchoSwarm differential drive</p><h1 id="name">ECHO Scout</h1>
<div class="row"><span id="link">connecting</span><span id="motion">CSI idle</span></div><div class="bar"><i id="level"></i></div>
<div class="grid"><i class="blank"></i><button data-x="0" data-y="100">▲</button><i class="blank"></i><button data-x="-100" data-y="0">◀</button><button class="stop" id="stop">■</button><button data-x="100" data-y="0">▶</button><i class="blank"></i><button data-x="0" data-y="-100">▼</button><i class="blank"></i></div>
<label>Speed <output id="speedOut">35%</output></label><input id="speed" type="range" min="10" max="70" value="35" style="width:100%">
<p class="muted">Motors stop when a button is released or commands disappear.</p></main><script>
const speed=document.querySelector('#speed'),out=document.querySelector('#speedOut');let timer;
speed.oninput=()=>out.value=speed.value+'%';
function stop(){clearInterval(timer);fetch('/stop').catch(()=>{});}function drive(x,y){stop();const send=()=>fetch(`/drive?x=${x}&y=${y}&speed=${speed.value}`).catch(()=>stop());send();timer=setInterval(send,150)}
document.querySelectorAll('[data-x]').forEach(b=>{b.onpointerdown=e=>{e.preventDefault();drive(b.dataset.x,b.dataset.y)};b.onpointerup=stop;b.onpointercancel=stop;b.onpointerleave=stop});document.querySelector('#stop').onclick=stop;onblur=stop;
setInterval(()=>fetch('/status').then(r=>r.json()).then(s=>{name.textContent=s.name;link.textContent='online · '+s.ip;motion.textContent=s.motion?'CSI disturbance':'CSI idle';level.style.width=Math.min(100,s.motion_level)+'%'}).catch(()=>link.textContent='no link'),500);
</script></body></html>
)HTML";

void configureServer() {
  server.on("/", HTTP_GET, []() { server.send_P(200, "text/html", CONTROL_PAGE); });
  server.on("/drive", HTTP_GET, handleDrive);
  server.on("/stop", HTTP_GET, handleStop);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/motion", HTTP_GET, handleStatus);  // Backward-compatible alias.
  server.onNotFound([]() { sendJson("{\"error\":\"not found\"}", 404); });
  server.begin();
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);
  WiFi.setSleep(false);
  WiFi.setHostname(robotHost());
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.printf("%s connecting to %s", robotName(), WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print('.');
  }
  Serial.printf("\nWi-Fi connected. IP address: %s\n", WiFi.localIP().toString().c_str());
  Serial.printf("Scout control page: http://%s.local/\n", robotHost());
  Serial.println("Pi dashboard: http://10.42.0.1/");
  Serial.println("Registering with Pi at 10.42.0.1:8080...");
}

void setup() {
  Serial.begin(115200);
  delay(300);

  drivetrain.setBrake();
  stopMotors();

  connectWiFi();
  mdnsStarted = MDNS.begin(robotHost());
  if (mdnsStarted) {
    MDNS.addService("http", "tcp", 80);
    Serial.printf("mDNS ready: http://%s.local/\n", robotHost());
  } else {
    Serial.println("mDNS failed; Pi registration will still work by IP.");
  }
  csiUdp.begin(0);
  startCsi();
  configureServer();
  if (xTaskCreate(piRegistrationTask, "pi-registration", 4096, nullptr, 1, nullptr) != pdPASS) {
    Serial.println("Could not start HTTP registration task; UDP heartbeat remains active.");
  }
  lastCommandAt = millis();
}

void loop() {
  server.handleClient();
  processCsi();
  sendHeartbeat();

  if (!motorsStopped && millis() - lastCommandAt > COMMAND_TIMEOUT_MS) stopMotors();

  if (WiFi.status() != WL_CONNECTED) {
    stopMotors();
    if (millis() - lastWiFiAttemptAt >= WIFI_RETRY_MS) {
      lastWiFiAttemptAt = millis();
      WiFi.reconnect();
    }
  }
  delay(2);
}
