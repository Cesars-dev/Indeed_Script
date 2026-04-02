# CDP connect_over_cdp Hangs After Cookie Injection — Deep Search Prompt

## The Problem (Updated)

`rebrowser_playwright.connect_over_cdp()` hangs indefinitely on certain AdsPower browser profiles. We've isolated the root cause to **cookies stored in the browser profile**.

## Proof (Controlled Experiment)

We ran a definitive A/B test:

| Test | Profile State | CDP Result |
|------|--------------|------------|
| Brand new profile, no proxy, no cookies | Fresh | ✅ 0.1s |
| Brand new profile, WITH proxy (socks5), no cookies | Fresh + proxy | ✅ 0.1s |
| Brand new profile, WITH proxy, WITH 155 cookies injected via `Storage.setCookies` | Fresh + proxy + cookies | ❌ 15s timeout |
| Original broken profile, fingerprint_config overwritten via API | Modified | ❌ 15s timeout |
| Original broken profile, noise settings disabled in GUI | Modified | ❌ 15s timeout |

**Conclusion: Cookies cause the hang.** Not the proxy. Not the OS. Not the fingerprint noise. Not the group. The cookies.

## What The Cookies Look Like

155 cookies across these domains:
- `.indeed.com` (59 cookies) — includes `cf_clearance`, `__cf_bm`, `__Secure-PassportAuthProxy-*`, `CSRF`, etc.
- `.google.com`, `.doubleclick.net` — tracking cookies
- `.protonmail.com`, `.proton.me` — email session cookies (3 cookies)
- `.linkedin.com` — 1 cookie
- `.hubspot.com`, `.hsforms.com` — tracking (3 cookies)
- `.fpjs.io` — fingerprint JS cookie (1 cookie)
- `.clarity.ms` — Microsoft Clarity (1 cookie)
- Various Indeed subdomains: `secure.indeed.com`, `apply.indeed.com`, `smartapply.indeed.com`, `authentication-session-manager.indeed.com`

Notable cookies that could interfere:
1. **`cf_clearance`** (`.indeed.com`, httpOnly) — Cloudflare challenge clearance token
2. **`__cf_bm`** — Cloudflare bot management cookies (6 of them, across indeed subdomains)
3. **`_cfuvid`** — Cloudflare unique visitor ID
4. **`__Secure-PassportAuthProxy-BearerToken`** / `RefreshToken` / `OauthHMAC` / `OauthExpires` — Indeed OAuth tokens with `__Secure-` prefix (require HTTPS + Secure flag)
5. **`_iidt`** (`.fpjs.io`, httpOnly) — FingerprintJS device ID

## Environment

| Component | Version |
|-----------|---------|
| OS | Ubuntu 24.04 LTS (VPS, headless Xvfb) |
| Python | 3.13 |
| rebrowser-playwright | 1.52.0 |
| AdsPower | Headless, port 30025 |
| Chrome | 134 (SunBrowser kernel) |
| REBROWSER_PATCHES_RUNTIME_FIX_MODE | addBinding |

## Architecture

```
Python script
  └─ rebrowser_playwright 1.52.0
      └─ Playwright Server (bundled Node.js)
          └─ WebSocket → Chrome CDP port
```

When `connect_over_cdp()` is called:
1. Playwright Server connects WebSocket to Chrome ✅ (confirmed by logs: `<ws connected>`)
2. Server sends CDP initialization commands (Runtime.enable, Page.enable, etc.)
3. **HANGS HERE** — never completes browser attachment

Raw WebSocket (Python `websockets` library) connects instantly to the same port and can execute CDP commands like `Storage.getCookies` without issue.

## Key Questions

1. **Can Cloudflare cookies (`cf_clearance`, `__cf_bm`) cause Chrome's CDP to stall?** These cookies trigger Cloudflare's JS challenges on page loads. When Playwright attaches and initializes pages, does Chrome execute Cloudflare challenge JS that blocks the CDP event loop?

2. **Do `__Secure-` prefixed cookies (like Indeed's OAuth tokens) cause issues on non-HTTPS CDP connections?** The CDP connection is `http://127.0.0.1:{port}` (plain HTTP). `__Secure-` cookies require HTTPS. Could Chrome stall when it encounters these cookies during Playwright's page initialization?

3. **Does FingerprintJS (`_iidt` from `.fpjs.io`) inject runtime code that blocks Playwright's `addBinding` patch?** `rebrowser_playwright` uses `Runtime.addBinding` to avoid detection. FingerprintJS actively detects automation tools. Could their cookie trigger anti-detection JS that deadlocks with rebrowser's patches?

4. **Is there a known issue where `Storage.setCookies` via CDP causes subsequent `connect_over_cdp` to hang?** The cookies were injected via raw CDP `Storage.setCookies`. Does this method store cookies differently than normal browsing, causing Chrome to enter a bad state on next CDP attach?

5. **Would injecting ONLY the essential Indeed session cookies (CSRF, auth tokens) avoid the hang, while excluding Cloudflare/tracking cookies?** If the issue is volume or specific cookies, a selective injection might work.

6. **Is there a way to "warm" the browser after cookie injection before calling `connect_over_cdp`?** For example, navigating to `about:blank` via raw CDP first, then connecting Playwright.

## What We Need

A method to either:
- **A)** Identify which specific cookies cause the CDP hang and exclude them during injection
- **B)** Find a workaround to connect Playwright to a browser that has these cookies loaded
- **C)** Use raw CDP (which works) instead of Playwright's `connect_over_cdp` for the initial connection, then hand off to Playwright somehow
