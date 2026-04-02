#!/bin/bash
# indeed-pipeline/start.sh — powers up AdsPower stack
# Usage: sudo bash /root/indeed-pipeline/start.sh

LOG="/root/indeed-pipeline/logs/orchestrator.log"
WAIT=60

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Xvfb..." | tee -a "$LOG"
systemctl start xvfb.service
sleep 2

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting AdsPower..." | tee -a "$LOG"
systemctl start adspower.service

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Waiting ${WAIT}s for AdsPower to initialize..." | tee -a "$LOG"
sleep "$WAIT"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] AdsPower ready on :50325 — pipeline can now run." | tee -a "$LOG"
systemctl is-active adspower.service
