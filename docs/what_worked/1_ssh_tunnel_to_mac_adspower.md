# SSH Reverse Tunnel — Mac AdsPower → VPS

## What It Does
Opens a reverse SSH tunnel so the VPS can call the Mac's AdsPower local API as if it were local.
Mac's AdsPower is already authenticated (via Google OAuth) and has all profiles synced.

## The Command (run on Mac)
```bash
ssh -o StrictHostKeyChecking=no -o ExitOnForwardFailure=yes -fNR 50325:localhost:50325 root@45.55.90.156
```
- `-R 50325:localhost:50325` — binds VPS port 50325 to Mac's port 50325
- `-fN` — background, no remote command
- `-o ExitOnForwardFailure=yes` — exits cleanly if port already bound

## Verify Tunnel Is Working (run on VPS)
```bash
curl -s "http://localhost:50325/api/v1/user/list?page=1&page_size=3&api_key=6690380481d7de70c40230dca72e9403005bda7f364e3e6f"
```
Expected: `{"code":0,"data":{"list":[...]}}` with profile names.

## SSH Key Is Already Set Up
No password needed — `~/.ssh/id_rsa` is already authorized on `root@45.55.90.156`.
All SSH commands to VPS work without a password prompt.

## Caveat
The tunnel dies when:
- Mac sleeps / reboots
- This terminal session closes (if `-f` is not used)

For persistence, consider `autossh`:
```bash
brew install autossh
autossh -M 0 -o "ServerAliveInterval 30" -fNR 50325:localhost:50325 root@45.55.90.156
```

## AdsPower API — Correct Endpoint Format
```
GET http://localhost:50325/api/v1/user/list?page=1&page_size=100&api_key=YOUR_KEY
```
The `api_key` MUST be a query parameter — NOT a header, NOT inline auth.

## Mac AdsPower Port
Confirmed port: **50325** (PID 45208 main process).
Cross-check: `lsof -nP -iTCP -sTCP:LISTEN | grep -i ads`

## Credentials
- VPS: `root@45.55.90.156`
- AdsPower API key: `6690380481d7de70c40230dca72e9403005bda7f364e3e6f`
