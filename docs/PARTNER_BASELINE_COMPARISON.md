# Verified partner baseline comparison

This project is an integration and extension of the partner team's working
baseline at
[`AloeVeraZ/CityTechClubProjects/stem-research-academy`](https://github.com/AloeVeraZ/CityTechClubProjects/tree/main/stem-research-academy),
reviewed from its `main` branch on 2026-08-12. It is not a replacement
drivetrain design.

## Retained exactly from the tested baseline

| Subsystem | Partner baseline | Current 3TSahur/LARP implementation | Compatibility result |
| --- | --- | --- | --- |
| Mecanum GPIO layout | BCM FL `5/6`, RL `16/19`, FR `20/21`, RR `13/26` | Same `DEFAULT_MOTOR_PINS` mapping | No Pi motor pin changes. |
| Mecanum mixer | Forward, strafe, rotation normalization | Same wheel mix and normalization | Same expected mecanum motion model. |
| Direction reversal safety | One shared 15 ms zero-power dead-time | Same shared dead-time | Avoids sequential per-wheel reversal delays. |
| Motor software safety | Locked drive path and 200 ms Pi watchdog | Same drive API and watchdog | A stale browser command stops rather than replays. |
| Browser command strategy | Latest-command-only channel, 300 ms expiry, sequence checks, urgent stop abort | Retained | This is the partner method that prevents command backlog. |
| LARP transport | Per-scout command lock, HTTP drive/stop/status proxy, heartbeat registration | Retained and renamed for LARP A/B | Existing ECHO controller architecture remains in use. |
| LARP drive safety | Retained ECHO motor IDs left `1`, right `6`; 500 ms controller watchdog | Same | No ECHO motor mapping change. |
| Wi-Fi station behavior | `WiFi.setAutoReconnect(true)` and `WiFi.setSleep(false)` | Same | Avoids ESP32 power-save latency while connected. |

## Additions and intentional changes

| Area | Partner baseline | Current extension | Why it remains compatible |
| --- | --- | --- | --- |
| Names/network | Mecanum/ECHO names and `EchoSwarm` defaults | 3TSahur, LARP A/B, `3TSahur-Swarm` defaults | Every Pi, LARP, and camera configuration uses the same local network values. |
| Dashboard layout | Mecanum plus both scout panels visible together | Three keyboard-accessible robot tabs | A tab switch stops all robots and only one MJPEG feed remains open. |
| Video | C270 and scout streams | C270 plus dedicated Inland ESP32-CAM A/B streams | Video is isolated from drive routes; inactive feeds are removed. |
| Discovery | Scout heartbeat/HTTP registration | Same, with LARP labels and camera URLs | Dynamic heartbeat IP still overrides an mDNS fallback. |
| CSI | Scout status forwarding | CSI indicator and calibration UI | CSI remains advisory; it cannot block drive control. |
| Vision/tools | No optional inference toolchain | Optional per-feed YOLO, snapshots, health, timeline, gamepad, dead-man mode | Each is optional and failure-isolated from drive/stop paths. |
| C270 gimbal/ramp | Not present | Disabled-by-default actuator staging UI/API | No pin/channel/PWM output is enabled until hardware data is supplied. |

## Latency method: copied, then tightened safely

The partner baseline's key anti-latency design is already preserved: it keeps
only the newest browser command, expires commands after 300 ms, rejects stale
sequences, stops after a 200 ms Pi watchdog, and uses a single 15 ms direction
reversal dead-time. Those mechanisms are more important than simply sending
commands faster, because they prevent delayed movement after an input is no
longer current.

The current integration adds control-priority tuning around—not inside—that
proven motor path:

| Traffic/control detail | Partner baseline | Current tuning | Motor compatibility impact |
| --- | --- | --- | --- |
| Browser stale-request budget | 180 ms | 140 ms | A late command is dropped sooner; current replacement commands still use the retained sequence/expiry path. |
| Held LARP command refresh | 100 ms | 80 ms | Matches the partner's 80 ms mecanum cadence without changing LARP motor values. |
| Pi-to-LARP HTTP timeout | 200 ms | 120 ms, configurable by `SCOUT_REQUEST_TIMEOUT_SECONDS` | An unreachable LARP fails faster instead of occupying a request. |
| LARP CSI/status polling | Both scouts every 2 s | Skip a driven scout; inactive polls every 5 s, active-tab poll every 1.2 s | Auxiliary telemetry yields to motor control. |
| Wi-Fi reconnect cadence | Both controller/camera images retry every 5 s | Staggered controller 1.8/2.2 s; camera 2.0/2.4 s | Faster recovery with reduced synchronized retry bursts. |
| Video airtime | Existing shared hotspot | One active dashboard stream and 10 FPS ESP32-CAM cap | Preserves capacity for short control packets. |
| Repeated held commands | Every heartbeat reapplies the same motor output | Identical Pi PWM and LARP drivetrain writes are skipped while watchdog timestamps still refresh | Reduces control-loop work without changing output, command cadence, or safety timeouts. |

The motor pins, mixer, PWM frequency, ECHO motor IDs, command endpoints,
watchdogs, and controller `WiFi.setSleep(false)` behavior are intentionally not
changed by this tuning.

## Compatibility and performance evidence

The isolated desktop suite currently passes **60 tests**, including the
three-robot compatibility test. It registers both LARPs with distinct simulated
hotspot addresses, sends a current 3TSahur command plus a command to each LARP,
and verifies both LARP status routes and the hub motor state.

The latest 100-cycle mocked composite run averaged **0.466 ms** locally, with
**0.697 ms** p95 and **1.042 ms** maximum. The preceding mocked run was
0.473 ms average / 0.770 ms p95 / 1.179 ms maximum. This is consistent with
the control path remaining short, but test-client timing is not evidence of a
measurable physical speed improvement. It cannot measure real hotspot airtime,
ESP32 scheduling, battery voltage drop, motor noise, or radio interference.

Use the [latency tuning guide](LATENCY_TUNING.md) and
[field information checklist](FIELD_INFORMATION_CHECKLIST.md) while testing
the actual robots. Record results with one camera stream active, then identify
the first optional feature that changes latency before modifying the retained
motor architecture.
