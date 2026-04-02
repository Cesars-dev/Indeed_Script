# Memory Archive — Sessions 1–3 (pre Session 4)

> Historical record. Do not use for active decisions — see `temporal_memory.md` instead.

---

## Dead Approaches (never retry)

### Approach 1: Headless Chrome on VPS (M1–M6)
- Cloudflare kills at TLS handshake. Page never loads. Archived: `archive/nodriver/`.

### Approach 2: Cookie Injection + Headless (M1–M6)
- Cookies don't fix the fingerprint. macOS Keychain encrypts Chrome cookies — can't copy sqlite file.

### Approach 3: AdsPower + nodriver (M7–M22)
- `connection_url` kwarg silently ignored — nodriver launches its own Chrome instead of attaching
- `best_match=True` matched wrong elements (nav bar instead of Apply button)
- WebSocket 500 crashes mid-session
- 15-step hardcoded state machine broke on every Indeed layout change
- Archived: `archive/nodriver/nodriver_indeed.py`

### Why not pyppeteer?
- Last release Oct 2022 — abandoned. Playwright is the maintained successor.

---

## Architecture Decision Log

### Why Playwright over nodriver?
- nodriver: no `get_by_role()`, `get_by_label()`, unpredictable timeouts, WebSocket 500 crashes
- Playwright auto-waits, battle-tested CDP, Microsoft-maintained

### Why Gemini Vision over hardcoded selectors?
- SmartApply DOM changes randomly — selectors break silently
- Gemini reads the rendered form and decides the right action dynamically
- Cost: ~1 call per form step × ~8 steps × N applications

### Claude vs Gemini for Vision?
- Both work. Claude 3.5 Sonnet slightly better at structured JSON.
- Gemini 2.5 Flash already integrated. Swap is one line in `.env`.

### nodriver in attach mode adds zero value
- AdsPower handles ALL fingerprinting. nodriver's only advantage was behavioral helpers — these are replicated in Playwright with `mouse.wheel()` + `humancursor-playwright`.

---

## CF / Bot Detection Research (NDSS PRISM 2026)

Indeed runs a 6-feature ML model layered on top of Cloudflare + HUMAN/PerimeterX:

| Feature | Rule |
|---------|------|
| `isTrusted` | Always use Playwright input APIs — CDP events are already trusted |
| Honeypot triggered | Gemini prompt must exclude hidden/zero-size/disabled elements |
| Velocity per minute | 3–12s delays between major actions |
| `timeToPreview` | Wait 4–10s on results before previewing, 10–30s before clicking Apply |

**Banned patterns:**
- `window.scrollBy()` — generates zero WheelEvents. Use `page.mouse.wheel()`.
- `page.hover()` for behavioral actions — single-point teleport. Use Bezier + manual click.
- `window.dispatchEvent()` — `isTrusted=false`. Always use Playwright input APIs.

**Playwright globals to neutralize after `connect_over_cdp()`:**
```python
await context.add_init_script("""
(() => {
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
  try { delete window.__playwright__binding__; } catch(e) {}
  try { delete window.__pwInitScripts; } catch(e) {}
})();
""")
```

---

## SmartApply — Historical Notes

### Entry flow
```
viewjob?jk=... → CSS selectors for Apply button → click → smartapply.indeed.com/beta/...
```
Old bug: `best_match=True` clicked gnav-util-viewjob (nav bar). Fixed with CSS selectors + `best_match=False`.

### Continue button trap
Button often below fold. Old code matched "Save and close" (visible at top) → exited SmartApply.
Fix: scroll down first → `button[type='submit']` → exact text match.

### Settings redirect
`secure.indeed.com/settings` → account has no Indeed Resume. Fast-fail: detect + return `failed`.

---

## Session 1–2 Accomplishments
- Phase 1 complete: RUN_MODE, humanization layer, LibreOffice on VPS, deps installed
- ADSPOWER_API_KEY added to `.env`
- VPS code path: `/root/projects/indeed-pipeline/` (old archived at `/root/indeed-pipeline.archived/`)
- VS Code browser tunnel: `ssh -L 8888:localhost:8888 root@45.55.90.156` → `http://localhost:8888`
- `playwright_indeed.py` written with full Gemini Vision loop
- `apply_runner.py` wired to import from `playwright_indeed`
- 1 account (oswaldin.lara / k19td50a) has valid session + Indeed profile set up

## Session 3 Batch Run Results (stale — for reference only)

### Run 1 — `logs/batch_1772428296.jsonl` (23:16)
| Job | Status | Reason | Time |
|---|---|---|---|
| 1 | failed | Timed out 180s — CF-fatigued mid-run | 269s |

### Run 2 — `logs/batch_1772429147.jsonl` (23:27)
| Job | Status | Reason | Time |
|---|---|---|---|
| 1 | failed | CF captcha — profile fatigued | 97s |
| 2 | failed | No apply button (CF block) | 110s |
| 3 | failed | CF on SmartApply | 29s |

CF pattern: first run in a session always works; after 3+ runs same session → consistent CF on all URL types.

---

## VPS Infrastructure Reference

| Service | Command |
|---------|---------|
| Webhook server | `systemctl status indeed-webhook` (port 8080) |
| AdsPower (headless) | `systemctl status adspower.service` (port 20725 — Forbidden without device registration) |
| Xvfb | `systemctl status xvfb.service` (:99) |
| Cron | `crontab -l` → `0 9 * * *` orchestrator.py |

**AdsPower port rule:** Port `20725` = VPS-native, device-bound → returns `Forbidden`. Always use `50325` (Mac tunnel).

```bash
# VPS control (from Mac)
bash scripts/vps_adspower.sh start|stop|status|diagnose|restart

# Tunnel (must be running before any VPS script)
bash scripts/tunnel.sh
# Forwards: Mac:50325 ←── VPS:50325 (reverse) | Mac:3001 ──→ VPS:3001
```

---

## Gmail Accounts Pool (not yet in AdsPower)

From `gmail_accounts` Supabase table:
- trcharly347, eljuande1965, angelivanlopez72, limonrangel308, ellukistrike
- erickssson528, mconchita521, alejandralizzete, rodriguesmurillogabriela
- ~~ochoachoaguillermomemo~~ (causes browser crash — do NOT use)
- abrahamibarrapadilla297, samaranaestro, fmgutierrez123, jonathanjonadidi

For new accounts: use Outlook/Hotmail (no phone verify, less Google friction).

---

## Session Injection Process (8 profiles still need this)

1. Firefox (personal IP, no proxy) → Gmail login → indeed.com login
2. `python3 scripts/inject_firefox_cookies.py --user-id <id>`
3. Wait 24h — CF needs time to score as returning human
4. Open AdsPower profile → any job → Apply → complete Indeed profile wizard once
5. Profile is now warm

Firefox cookies are plain SQLite (no Keychain encryption) — readable with Python `sqlite3`.

---

## CDP Port Discovery (run once per profile)

Record fixed debug port per profile — needed to add per-profile `-L` entries to `tunnel.sh`:

```bash
for uid in k19td4st k19td4tu k19td4uh k19td4v5 k19td4vp k19td4wc k19td4x8 k19td4xs k19td50a; do
  port=$(curl -s "http://localhost:50325/api/v1/browser/start?user_id=$uid&api_key=$(grep ADSPOWER_API_KEY .env | cut -d= -f2)" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['ws']['puppeteer'].split(':')[2].split('/')[0])" 2>/dev/null)
  echo "$uid → $port"
done
```

Then add one `-L <port>:localhost:<port>` per profile to `scripts/tunnel.sh`.
