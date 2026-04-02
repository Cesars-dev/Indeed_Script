# Memory: Sessions & Account Management

## The Real Session Cookie

**`JSESSIONID` is the session** — not `indeed_sess` (obsolete) or `CTK` (tracking-only, always present).

Old scripts falsely validated sessions by checking `CTK` → reported "Session confirmed" on CF challenge pages.
All session validation must check: `{"JSESSIONID", "INDEED_CSRF_TOKEN"}`.

## Session Lifecycle

1. Fresh AdsPower profile + proxy → zero history → Cloudflare scores HIGH risk → Turnstile fires
2. Manual one-time login via Firefox (personal IP, no proxy):
   - Open Firefox → Gmail login → indeed.com login  
   - Run `scripts/inject_firefox_cookies.py --user-id <id>`  
   - This copies Firefox SQLite cookies → AdsPower profile via API
3. **Wait 24h** — CF needs time to score the profile as a returning human
4. Profile is now warm — scripts can navigate without Turnstile  

## Why Google Blocks AdsPower Logins

New AdsPower profile + residential proxy = new device fingerprint → Google blocks Gmail login with SMS/captcha.

**Solution**: Log in via personal Mac Firefox (no proxy, known IP) → extract cookies → inject into AdsPower.

**Firefox extraction**: cookies are plain SQLite (no Keychain encryption), readable with Python's `sqlite3`.

Script: `scripts/inject_firefox_cookies.py --user-id <user_id>`

## Profile Health Rules

1. **Never restart profiles repeatedly** — each stop/start risks cookie loss
2. **Burned proxies stay burned** — CF ties IP history to risk score; rotate to fresh proxies on reset
3. **22h sleep between sessions** — after login, let the profile rest
4. **AdsPower is ground truth** for email ↔ profile mapping — Supabase can go stale
5. **`setup_profiles.py` deletes ALL indeed-group profiles** — always verify Supabase matches after running
6. VPS-native AdsPower (port 20725) requires device registration → sessions expire after ~1 load cycle
   - **Always use Mac tunnel (port 50325)** — it's stable and device-bound to Mac

## Indeed Profile Setup (one-time per account)

Even with valid cookies, clicking Apply redirects to `/settings` if no Indeed Resume exists.

Per account, ONE TIME:
1. Open AdsPower profile → browse to `indeed.com` (already logged in after cookie injection)
2. Click any job → "Apply with Indeed"
3. Complete the wizard: upload/build resume, set visibility, answer profile questions
4. After this, SmartApply opens normally forever

**Done:** `k19td50a` (oswaldin.lara@gmail.com) ✅

**Needs setup:** All other 8 profiles

## Available Gmail Accounts (not in AdsPower yet)

From `gmail_accounts` Supabase table — 14 available accounts in pool:
- trcharly347, eljuande1965, angelivanlopez72, limonrangel308, ellukistrike
- erickssson528, mconchita521, alejandralizzete, rodriguesmurillogabriela
- ochoachoaguillermomemo (causes browser crash — do not use)
- abrahamibarrapadilla297, samaranaestro, fmgutierrez123, jonathanjonadidi

**For new accounts**: Use Outlook/Hotmail (no phone verify, free, less Google friction)

## Phone Numbers (for SmartApply forms)

| Email | Phone |
|-------|-------|
| oswaldin.lara@gmail.com | +12068819903 |
| others | — (add as SmartApply requests them) |
