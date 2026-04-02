#!/bin/bash
# scripts/vps_adspower.sh — Control AdsPower on VPS from Mac
#
# Usage:
#   bash scripts/vps_adspower.sh start    → Start Xvfb + AdsPower (waits 60s)
#   bash scripts/vps_adspower.sh stop     → Kill AdsPower + Xvfb, free RAM
#   bash scripts/vps_adspower.sh status   → Check service state + API health
#   bash scripts/vps_adspower.sh restart  → stop then start
#   bash scripts/vps_adspower.sh diagnose → Full service + process + log dump
#
# IMPORTANT — Port 30025 (VPS-native AdsPower API):
#   Port 30025 = VPS AdsPower API (headless, --api-key auth) — WORKING
#   Port 20725 = ghost-locked by AdsPower internals — do NOT use
#   Port 50325 = Mac tunnel (legacy, still works if Mac is on)
#
# Requires: SSH key auth to root@45.55.90.156

VPS="root@45.55.90.156"
CMD="${1:-status}"

_status() {
    echo "[vps_adspower] Checking VPS AdsPower status..."
    ssh "$VPS" "
        echo '--- Services ---'
        systemctl is-active xvfb.service    && echo 'xvfb:     ACTIVE' || echo 'xvfb:     INACTIVE'
        systemctl is-active adspower.service && echo 'adspower: ACTIVE' || echo 'adspower: INACTIVE'
        echo ''
        echo '--- VPS AdsPower API (port 30025) ---'
        curl -s --max-time 5 'http://localhost:30025/api/v1/user/list?api_key=6690380481d7de70c40230dca72e9403005bda7f364e3e6f&page=1&page_size=1' | head -c 120
        echo ''
        echo '--- Xvfb display :99 ---'
        DISPLAY=:99 xdpyinfo 2>&1 | grep 'name of display' || echo 'Xvfb :99 not responding'
        echo ''
        echo '--- RAM ---'
        free -h | grep Mem
        echo ''
        echo '--- Last 5 log lines ---'
        tail -5 /root/indeed-pipeline/logs/orchestrator.log 2>/dev/null || echo 'No log'
    "
}

_start() {
    echo "[vps_adspower] Starting AdsPower on VPS (takes ~60s)..."
    ssh "$VPS" "
        rm -f /root/.config/adspower_global/Singleton* 2>/dev/null
        systemctl start xvfb.service
        sleep 2
        systemctl start adspower.service
    "
    echo "[vps_adspower] Start command sent. Waiting 60s for AdsPower to initialize..."
    sleep 60
    echo "[vps_adspower] Verifying..."
    _status
}

_stop() {
    echo "[vps_adspower] Stopping AdsPower on VPS..."
    ssh "$VPS" "
        systemctl stop adspower.service 2>/dev/null || true
        pkill -f 'AdsPower' 2>/dev/null || true
        pkill -f 'adspower_global' 2>/dev/null || true
        systemctl stop xvfb.service 2>/dev/null || true
        echo 'Services stopped.'
        free -h | grep Mem
    "
    echo "[vps_adspower] Done."
}

_diagnose() {
    echo "[vps_adspower] Running full diagnostics..."
    ssh "$VPS" "
        echo '=== systemctl status xvfb ==='
        systemctl status xvfb.service --no-pager | tail -20

        echo ''
        echo '=== systemctl status adspower ==='
        systemctl status adspower.service --no-pager | tail -20

        echo ''
        echo '=== Processes ==='
        ps aux | grep -E 'Xvfb|AdsPower|adspower' | grep -v grep

        echo ''
        echo '=== Ports in use ==='
        ss -tlnp | grep -E '30025|50325|Xvfb'

        echo ''
        echo '=== Disk (AdsPower data) ==='
        du -sh /root/.config/adspower_global/ 2>/dev/null || echo 'No AdsPower data dir found'

        echo ''
        echo '=== Recent journal errors ==='
        journalctl -u adspower.service -n 30 --no-pager 2>/dev/null | grep -iE 'error|fail|fatal|crit' | tail -10 || echo 'No errors found'

        echo ''
        echo '=== Xvfb display check ==='
        DISPLAY=:99 xdpyinfo 2>/dev/null | head -5 || echo 'Xvfb display :99 not responding'
    "
}

case "$CMD" in
    start)   _start ;;
    stop)    _stop ;;
    status)  _status ;;
    restart) _stop && sleep 3 && _start ;;
    diagnose) _diagnose ;;
    *)
        echo "Usage: bash scripts/vps_adspower.sh [start|stop|status|restart|diagnose]"
        exit 1
        ;;
esac
