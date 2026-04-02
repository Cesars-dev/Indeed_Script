# AdsPower on VPS — Stable Systemd Service

## Status
AdsPower 7.3.26 runs stably on VPS with Xvfb. No GPU crashes.
The API however requires the SSH tunnel to Mac for authentication (see file 1).

## Wrapper Script — /opt/start-adspower.sh
```bash
#!/bin/bash
export DISPLAY=:99
export LIBGL_ALWAYS_SOFTWARE=1
exec "/opt/AdsPower Global/adspower_global" \
  --no-sandbox \
  --disable-gpu \
  --disable-software-rasterizer \
  --headless true \
  --api-key 6690380481d7de70c40230dca72e9403005bda7f364e3e6f \
  --api-port 50325
```
chmod +x /opt/start-adspower.sh

## Critical Flags
| Flag | Why |
|------|-----|
| `--no-sandbox` | Required when running as root on Linux |
| `--disable-gpu` | No GPU on VPS; prevents GPU subprocess crash |
| `--disable-software-rasterizer` | Prevents software GPU fallback crash |
| `LIBGL_ALWAYS_SOFTWARE=1` | Forces Mesa software GL (complements --disable-gpu) |
| `DISPLAY=:99` | Points to Xvfb virtual framebuffer |

## Systemd Service — /etc/systemd/system/adspower.service
```ini
[Unit]
Description=AdsPower Headless
After=xvfb.service
Requires=xvfb.service

[Service]
ExecStart=/opt/start-adspower.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Xvfb Service — /etc/systemd/system/xvfb.service
```ini
[Unit]
Description=Xvfb virtual display
After=network.target

[Service]
ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24
Restart=always

[Install]
WantedBy=multi-user.target
```

## Ubuntu 24 Dependency Fix
```bash
# libasound2 does NOT exist on Ubuntu 24 — use libasound2t64
sudo apt install -y xvfb libgbm1 libasound2t64 libxss1 \
  libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 \
  libatk-bridge2.0-0 libgtk-3-0 wget curl
# DO NOT install libgconf-2-4 — deprecated on Ubuntu 22.04+
```

## Binary Path (Space in Dir Name — Gotcha!)
```
/opt/AdsPower Global/adspower_global
```
Systemd ExecStart cannot handle spaces in paths → use a wrapper script (above).
Quoting the path in ExecStart does NOT work reliably.

## Actual Listening Port
`--api-port 50325` is **ignored** by AdsPower — it picks its own port (20725).
This doesn't matter when using the SSH tunnel approach (Mac serves on 50325).

## Process Health Check
```bash
systemctl status adspower          # should show active (running), 60+ tasks
journalctl -u adspower -n 20 --no-pager  # look for "did-finish-load"
```
