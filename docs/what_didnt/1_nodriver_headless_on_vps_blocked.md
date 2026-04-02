# FAILED: nodriver Headless Chrome on VPS — Blocked by Indeed

## What We Tried
Ran Python nodriver (headless Chrome) on VPS with:
- Webshare datacenter proxies
- Residential SOCKS5 proxy (45.147.159.35 via AdsPower profile kyrcyv3)
- Patched navigator.webdriver = false
- Cookie injection via CDP

## Result
9/9 test runs blocked. Indeed homepage returned "Blocked - Indeed.com" before even reaching a job page.

## Root Cause
Indeed uses Cloudflare Bot Management which fingerprints at multiple layers:
1. **TLS/JA3 fingerprint** — Headless Chrome on Linux has a different TLS handshake signature than real Chrome
2. **Canvas fingerprint** — headless renders differently
3. **WebGL fingerprint** — no real GPU, reports software rasterizer
4. **Plugin count** — 0 plugins in headless
5. **Screen resolution** — reports 800×600 default

The residential IP correctly routes through 45.147.159.35, confirmed via `curl --socks5`. But Indeed detects the *browser*, not just the IP. Even with correct IP + webdriver=false, the TLS/JA3 signature at the network layer betrays headless Chrome.

## What navigator.webdriver = false Does NOT Fix
- TLS fingerprint (server-side, before JS runs)
- Canvas/WebGL entropy differences
- Missing plugins and extensions

## Why AdsPower Works
AdsPower spoofs ALL fingerprints:
- Custom TLS/JA3 via patched Chromium
- Canvas noise injection
- WebGL vendor/renderer spoofing
- Fake plugin enumeration
- Realistic screen resolution and device memory

## Lesson
For Indeed specifically, `navigator.webdriver = false` + residential proxy is NOT enough. You need a full anti-detect browser. Do NOT waste time trying to harden nodriver — the detection is at layers nodriver cannot touch.
