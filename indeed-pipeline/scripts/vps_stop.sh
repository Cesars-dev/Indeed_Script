#!/bin/bash
# indeed-pipeline/stop.sh — powers down AdsPower stack to free RAM
# Usage: sudo bash /root/indeed-pipeline/stop.sh

LOG="/root/indeed-pipeline/logs/orchestrator.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Stopping AdsPower..." | tee -a "$LOG"
systemctl stop adspower.service 2>/dev/null || true
pkill -f "AdsPower" 2>/dev/null || true

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Stopping Xvfb..." | tee -a "$LOG"
systemctl stop xvfb.service 2>/dev/null || true

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done. RAM freed." | tee -a "$LOG"
free -h | grep Mem
