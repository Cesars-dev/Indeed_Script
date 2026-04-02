# FAILED: Datacenter IPs Blocked by Indeed

## What We Tried
- Webshare datacenter proxies (100 US IPs) via `--proxy-server` in Chrome
- Custom HTTP CONNECT relay (proxy_relay.py) to inject Proxy-Authorization header
- Rotating proxies: accounts 1, 4, 7 on relay ports 8904/8905/8906

## Result
9/9 blocked on the Indeed homepage itself. Not even reaching job pages.

## Root Cause
Datacenter IP ranges (DigitalOcean, AWS, etc.) are trivially fingerprinted:
- ASN lookup instantly identifies them as hosting providers
- Indeed (via Cloudflare) blocklists entire ASN blocks
- Doesn't matter how many different IPs you rotate

## Why The Relay Was Needed (separate issue)
Chrome strips inline credentials from `--proxy-server=user:pass@host:port`.
Chrome removes the `user:pass@` part silently. Custom relay (proxy_relay.py) listens
unauth locally, then injects the Proxy-Authorization header upstream.

## pproxy Also Failed
`pproxy` doesn't support authenticated upstream HTTP proxies — it interprets
`user:pass` as a cipher name, not credentials.

## Lesson
Webshare datacenter proxies work for scraping generic sites. For Indeed specifically,
they are blocked before any automation even runs. Use residential proxies only,
AND pair with an anti-detect browser (AdsPower).

## Files (can be deleted or kept for reference)
- `/root/indeed-pipeline/proxy_relay.py` — custom HTTP CONNECT relay
- `/root/indeed-pipeline/socks5_relay.py` — custom SOCKS5 relay for residential proxy
- `/root/indeed-pipeline/stress_test_v3.py` — failed stress test with datacenter IPs
- `/root/indeed-pipeline/stress_residential.py` — failed stress test with residential IP + nodriver
