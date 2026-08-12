# Changes from the original project and partner integration base

## Integration base retained

The partner repository supplied the canonical project structure: `robot_server`
package, responsive keyboard/touch dashboard, NetworkManager hotspot, systemd
services, Chromium control-window support, atomic installer updates/rollback,
and a broad test suite. These are retained rather than replaced by the earlier
single-file prototype.

## 3TSahur/LARP integration

- Renamed the hub to **3TSahur** and the scouts to **LARP Scout A/B**.
- Changed default network and mDNS names to `3TSahur-Swarm`, `3tsahur.local`,
  `larp-a.local`, and `larp-b.local`.
- Added direct LARP camera panels to the existing dashboard.
- Moved/renamed the ECHO drive sketch to `firmware/larp-scout` and updated its
  station hostname and labels.
- Added a dedicated Inland ESP32-CAM firmware package with mDNS MJPEG streams.
- Reworked the dashboard into one tab per robot and keep only the selected
  camera stream open, preventing three simultaneous MJPEG feeds from consuming
  the Pi hotspot's control bandwidth.
- Made the LARP controller and camera Wi-Fi startup non-blocking, so either
  board can boot before the Pi hotspot and reconnect automatically. ESP32-CAM
  streams are capped at 10 FPS to reserve wireless capacity for controls.
- Added a LARP-tab CSI presence panel that visualizes the existing ECHO
  firmware's disturbance value while clearly requiring camera verification;
  added an Inland ESP32-CAM flashing and troubleshooting guide.

## Mecanum motor mapping

The Pi mecanum GPIO layout is intentionally unchanged from the partner base:
front-left `5/6`, rear-left `16/19`, front-right `20/21`, and rear-right
`13/26`. `robot_server/motor.py` and its associated simulation test enforce
that exact assignment.

## Documentation and verification

Added per-package READMEs, the setup and wiring guides, this change record, and
the recorded simulation results. The test suite now also checks LARP camera
firmware content and 3TSahur/LARP dashboard labels.

## Later operator and observability additions

The following additions are layered around—not inside—the partner-base motor
control path: one-active-stream robot tabs, C270 quality profiles, health
display, event timeline, snapshots, CSI calibration helper, browser gamepad,
dead-man mode, optional YOLO worker, and bounded feature polling. The latest
control tests continue to enforce route expiry/sequence checks and verify that
camera-profile, vision, snapshot, and timeline failures do not disable the
motor control API.

## Installer access

The base install workflow is retained. `installer/curl-install.sh` now offers
a small reviewable bootstrap command that downloads the versioned `install.sh`;
it does not duplicate or bypass the installer's atomic validation/rollback
workflow.
