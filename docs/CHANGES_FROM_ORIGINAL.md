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

## Confirmed motor correction

The partner base assumed Driver 1's second channel was rear-left and Driver
2's first channel was front-right. The confirmed physical arrangement is front
axle on Driver 1 and rear axle on Driver 2. `robot_server/motor.py` now maps
front-left `5/6`, front-right `16/19`, rear-left `20/21`, rear-right `26/13`.
The associated test now enforces it.

## Documentation and verification

Added per-package READMEs, the setup and wiring guides, this change record, and
the recorded simulation results. The test suite now also checks LARP camera
firmware content and 3TSahur/LARP dashboard labels.
