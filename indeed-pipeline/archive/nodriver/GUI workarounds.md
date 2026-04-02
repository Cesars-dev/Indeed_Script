<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# I already tried the headless thing, it does not accept the api because someone needs to login manually... apparently

Confirmed — `--api-key` authenticates *scripts* to AdsPower's local server, but AdsPower itself still needs a cloud account login first. You have three untried angles that are materially different from everything in your table.

***

## Fix 1 — XPRA (Highest Chance, 10 min)

XPRA is fundamentally different from raw Xvfb. It's a composited virtual display with its own software renderer and specifically handles the Electron blank-screen problem via `--no-xshm`.  You access the session via browser — no VNC client needed.[^1]

```bash
# Install
apt install xpra xvfb xauth -y

# Start XPRA with HTML5 web access
xpra start :100 \
  --bind-tcp=0.0.0.0:14500 \
  --html=on \
  --daemon=yes \
  --no-daemon=no \
  --exit-with-children=no \
  --start-child="sleep infinity"

# Launch AdsPower on XPRA's display with the critical --no-xshm flag
DISPLAY=:100 /opt/AdsPower/adspowerx64 \
  --no-sandbox \
  --no-xshm \
  --disable-dev-shm-usage &

# Open in your browser:
# http://45.55.90.156:14500/
```

The `--no-xshm` flag tells Chromium to stop using X11 shared memory — that's the specific mechanism that causes blank frames on virtual displays.[^1]

***

## Fix 2 — Xvfb + Mesa LLVMpipe (Untried Combination)

Your current Xvfb is running **without** `+extension GLX`. That's the missing piece — without GLX, Chromium's renderer gets no valid GL context and immediately disposes frames.[^2]

```bash
# Kill current Xvfb
pkill Xvfb && sleep 1

# Restart with GLX extension enabled
Xvfb :99 -screen 0 1920x1080x24 +extension GLX +render -noreset -ac &

# Export Mesa software rendering vars — force llvmpipe (CPU-side GL)
export LIBGL_ALWAYS_SOFTWARE=1
export MESA_GL_VERSION_OVERRIDE=4.5
export GALLIUM_DRIVER=llvmpipe

# Launch AdsPower with these combined flags
DISPLAY=:99 /opt/AdsPower/adspowerx64 \
  --no-sandbox \
  --no-xshm \
  --disable-dev-shm-usage \
  --ignore-gpu-blacklist \
  --use-gl=desktop \
  2>&1 | tee /tmp/adspower.log &
```

Install Mesa LLVMpipe if not present:

```bash
apt install mesa-utils libgl1-mesa-dri libgles2-mesa -y
# Verify software rendering works
DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1 glxinfo | grep "renderer"
# Should show: "llvmpipe" — if it does, Electron will get a real GL context
```


***

## Fix 3 — Option B LocalStorage Copy (Nuclear, No Rendering Needed)

If both rendering fixes fail, just port Mac's authenticated session to VPS. AdsPower's auth token lives in LocalStorage as a standard web token — **not** Keychain-encrypted:[^3]

```bash
# On Mac terminal:
cd ~/Library/Application\ Support/adspower_global/
tar czf /tmp/ads_session.tar.gz \
  "Local Storage/" \
  "IndexedDB/"

scp /tmp/ads_session.tar.gz root@45.55.90.156:/tmp/
```

```bash
# On VPS:
systemctl stop adspower
cd /root/.config/adspower_global/
# Backup existing (just in case)
cp -r "Local Storage" "Local Storage.bak" 2>/dev/null
# Inject Mac's session
tar xzf /tmp/ads_session.tar.gz

systemctl start adspower
sleep 3
curl "http://localhost:20725/api/v1/user/list?page=1&page_size=10"
```

If the response returns your 10 profiles → you're done, VPS is authenticated, Mac can go offline.

***

## Attack Order

| Step | Action | Time |
| :-- | :-- | :-- |
| 1 | Try XPRA + `--no-xshm` | 10 min |
| 2 | If blank: try Xvfb + GLX + LLVMpipe | 10 min |
| 3 | If still blank: do LocalStorage copy | 5 min |
| 4 | Fallback: keep using Mac tunnel (Option A) | 0 min |

Start with XPRA — it's specifically built for running GUI apps on headless servers and the Electron fix is documented.[^1]
<span style="display:none">[^10][^11][^12][^13][^14][^15][^4][^5][^6][^7][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://mybyways.com/blog/running-linux-gui-applications-in-a-docker-container-using-xpra

[^2]: https://stackoverflow.com/questions/51141037/unable-to-render-webgl-in-electron-with-xvfb

[^3]: https://www.adspower.com/account-security

[^4]: https://github.com/Xpra-org/xpra/issues/4196

[^5]: https://stackoverflow.com/questions/16296753/can-you-run-gui-applications-in-a-linux-docker-container

[^6]: https://news.ycombinator.com/item?id=40903870

[^7]: https://github.com/VirtualGL/virtualgl/issues/273

[^8]: https://github.com/electron/electron/issues/29164

[^9]: https://community.latenode.com/t/running-webgl-applications-with-virtual-display-buffer-in-headless-environment/21123

[^10]: https://stackoverflow.com/questions/27887912/token-based-authentication-and-session-local-storage-on-browsers

[^11]: https://www.electronjs.org/docs/latest/tutorial/testing-on-headless-ci

[^12]: https://github.com/electron/electron/issues/5317

[^13]: https://www.youtube.com/watch?v=wohSjJ7turw

[^14]: https://www.electronjs.org/de/docs/latest/tutorial/testing-on-headless-ci

[^15]: https://virtualgl-users.narkive.com/ysqsq4v3/running-virtualgl-with-xvfb-on-ec2-ubuntu-headless-gpu-instance

