# FAILED: AdsPower --api-key Flag Does NOT Replace Cloud Login

## What We Assumed
Running AdsPower with `--api-key YOUR_KEY` would authenticate it to the cloud and make the API work without GUI login.

## What Actually Happens
`--api-key` sets the key that **clients** must pass when calling the local API.
It does NOT log AdsPower into the AdsPower cloud account.

## Symptom
```
GET http://localhost:20725/api/v1/user/list?api_key=xxx → HTTP 401 "Forbidden"
GET http://localhost:20725/ → {"code":0,"data":{"version":"v2.8.3.3"}} (server alive)
```
Root endpoint works. All `/api/v1/` routes are forbidden because AdsPower has no cloud session.

## Also Failed: Copying Mac Session Files to VPS
Tried copying:
- `Local Storage/leveldb/` → Chromium cookies are **encrypted with macOS Keychain**
- `IndexedDB/` → Same encryption issue
- `Cookies` SQLite file → Keychain-encrypted, cannot be read on Linux

macOS uses DPAPI/Keychain to encrypt browser credentials. They cannot be transferred cross-platform.

## Also Failed: --api-port Flag
`--api-port 50325` is silently ignored. AdsPower picks its own port (20725 in our case).

## The Fix
Use the SSH reverse tunnel to Mac's already-authenticated AdsPower.
See: `what worked/1_ssh_tunnel_to_mac_adspower.md`

## Lesson
AdsPower's local API requires an active cloud session (GUI login). In headless/server mode, the only clean solution is:
1. SSH tunnel to an already-logged-in Mac instance (our solution)
2. VNC once to log in, then session persists in the data dir
