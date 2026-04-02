# FAILED: Wrong APT Package Names on Ubuntu 24.04

## Packages That Don't Exist on Ubuntu 24.04

### libasound2
```
E: Package 'libasound2' has no installation candidate
```
**Fix:** Use `libasound2t64` instead (64-bit transition package)

### libgconf-2-4
Deprecated and removed from Ubuntu 22.04+. AdsPower does not actually need it.
**Fix:** Simply omit it from the install list.

## Correct Install Command for Ubuntu 24.04
```bash
sudo apt install -y xvfb libgbm1 libasound2t64 libxss1 \
  libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 \
  libatk-bridge2.0-0 libgtk-3-0 wget curl
```

## AdsPower dpkg Error (not fatal)
```
dpkg: error processing package adspower-global (--install): dependency problems
```
Fix with: `sudo apt --fix-broken install -y`
The `update-desktop-database: command not found` warning that follows is harmless.

## Python stdout Buffering
Stress test logs were empty because Python buffers print() when output goes to a file.
**Fix:** Run with `python -u script.py` (unbuffered mode).

## nohup PID=0
Background SSH process showed PID=0. Caused by SSH session ownership issue.
**Fix:** Write a shell wrapper script and run that with nohup from within SSH.

## Systemd ExecStart with Spaces in Path
Binary path `/opt/AdsPower Global/adspower_global` has a space.
Quoting in ExecStart does NOT work reliably in all systemd versions.
**Fix:** Use a wrapper bash script (`/opt/start-adspower.sh`) that exec's the binary with quoted path.
