# 3TSahur installer

`install.sh` provisions Raspberry Pi OS for 3TSahur. It installs system
packages, creates the `3TSahur-Swarm` NetworkManager hotspot, deploys the
dashboard systemd service, configures mDNS and a Chromium control window, and
validates a replacement installation before atomically swapping it into place.

Run it as the normal Pi user—not as root—from a trusted checkout:

```bash
bash installer/install.sh
```

It intentionally reboots when complete. See [../docs/SETUP.md](../docs/SETUP.md)
for preparation, flashing order, and safety checks.
