On the VPS via SSH, perform a headless AdsPower installation:

STEP 1 — Install display + dependencies:
  sudo apt update
  sudo apt install -y xvfb libgbm1 libasound2 libxss1 \
    libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 \
    libatk-bridge2.0-0 libgtk-3-0 wget curl
  NOTE: Do NOT install libgconf-2-4 — deprecated/broken on Ubuntu 22.04+

STEP 2 — Create persistent Xvfb service:
  Create /etc/systemd/system/xvfb.service:
    [Unit]
    Description=Xvfb virtual display
    After=network.target

    [Service]
    ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24
    Restart=always

    [Install]
    WantedBy=multi-user.target

  sudo systemctl daemon-reload
  sudo systemctl enable xvfb
  sudo systemctl start xvfb
  systemctl status xvfb  # confirm active

STEP 3 — Download and install AdsPower:
  # Scrape index to find latest .deb filename
  curl -s https://version.adspower.net/software/linux-x64-global/ | grep -o 'AdsPower-Global-[0-9.-]*x64\.deb' | tail -1
  # Download it (currently 7.3.26):
  wget https://version.adspower.net/software/linux-x64-global/AdsPower-Global-7.3.26-x64.deb
  sudo dpkg -i AdsPower-Global-7.3.26-x64.deb
  sudo apt --fix-broken install -y

STEP 4 — Find binary path post-install:
  find /opt /usr -name "adspower*" -type f 2>/dev/null
  # Note the exact path — use it in Step 5

STEP 5 — Create AdsPower headless systemd service:
  # Replace BINARY_PATH with result from Step 4
  # Replace YOUR_API_KEY with the key from AdsPower → Settings → Local API
  Create /etc/systemd/system/adspower.service:
    [Unit]
    Description=AdsPower Anti-detect Browser (Headless)
    After=xvfb.service
    Requires=xvfb.service

    [Service]
    Environment="DISPLAY=:99"
    ExecStart=BINARY_PATH --headless true --api-key 6690380481d7de70c40230dca72e9403005bda7f364e3e6f --api-port 50325
    Restart=on-failure
    RestartSec=5

    [Install]
    WantedBy=multi-user.target

  sudo systemctl daemon-reload
  sudo systemctl enable adspower
  sudo systemctl start adspower
  sleep 8

STEP 6 — Verify API is up and profiles are synced:
  curl "http://localhost:50325/api/v1/user/list?page=1&page_size=100"
  Expected: {"code":0, "data": {"list": [...]}}
  Print full response — cloud profiles should appear immediately (API key = same account).

KEY FACTS:
  - --headless true is a real flag (requires AdsPower v3.3.2+, kernel v2.4.2.8+)
  - API key auth replaces GUI login — no VNC ever needed
  - Profiles are cloud-synced; they appear as soon as API key is authenticated
  - API key: AdsPower app (Mac) → Account → Settings → Local API → Generate Key
