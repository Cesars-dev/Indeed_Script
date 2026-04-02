#!/bin/bash
# VPS Tunnel — autossh keeps it alive through sleep/network changes
# Forwards:  localhost:3001-3003 → VPS GitHub MCP servers
# Reverse:   VPS:50325 → Mac AdsPower API
# Reverse:   VPS:52018 → Mac browser CDP debug port (fixed)

VPS="root@45.55.90.156"

# Kill any existing tunnels on these ports
lsof -ti:3001,3002,3003 | xargs kill 2>/dev/null
pkill -f "autossh.*45.55.90.156" 2>/dev/null

autossh -M 0 \
    -o StrictHostKeyChecking=no \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes \
    -fN \
    -L 3001:localhost:3001 \
    -L 3002:localhost:3002 \
    -L 3003:localhost:3003 \
    -R 50325:localhost:50325 \
    -R 52018:localhost:52018 \
    $VPS

echo "Tunnel up (autossh — survives sleep/reconnects automatically)"
echo "  localhost:3001-3003 → VPS GitHub MCP"
echo "  VPS:50325           → Mac AdsPower API"
echo "  VPS:52018           → Mac browser CDP (fixed debug port)"
