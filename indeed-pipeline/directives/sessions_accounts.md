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

## Current Profile Roster (as of 2026-03-30)

Source of truth: `config/profiles.json`

### Active (pending cookie activation — 16 profiles)

| Slot | Name | Email | Exp | Salary |
|------|------|-------|-----|--------|
| 1 | Gabriela Lopez Gomez | gabrielalopezgomez80@gmail.com | 3yr | $29k |
| 2 | Alexei Shon | alexeishon2@gmail.com | 5yr | $45k |
| 3 | Jonathan Garcia Ramos | garciaramosjonathan8@gmail.com | 4yr | $38k |
| 4 | Yoshi Porfirio | yoshiporfirioyoshio@gmail.com | 2yr | $28k |
| 5 | Hector Manuel Gutierrez Ramirez | gutierrezramirezhectormanuel6@gmail.com | 6yr | $52k |
| 6 | Jonathan Martinez Medina | martinezmedinajonathan975@gmail.com | 4yr | $36k |
| 7 | Clara Sanchez Villela | clarasanchezvillela@gmail.com | 3yr | $31k |
| 8 | Alis Fleet | alisfleet@gmail.com | 5yr | $42k |
| 11 | Alejandra Lizzete | alejandralizzete@gmail.com | 3yr | $30k |
| 12 | Angel Ivan Lopez | angelivanlopez72@gmail.com | 5yr | $48k |
| 13 | Elluki Strike | ellukistrike@gmail.com | 2yr | $25k |
| 14 | Erick Sson | erickssson528@gmail.com | 6yr | $58k |
| 15 | FM Gutierrez | fmgutierrez123@gmail.com | 3yr | $32k |
| 16 | Jonathan Jonadidi | jonathanjonadidi@gmail.com | 4yr | $40k |
| 17 | Limon Rangel | limonrangel308@gmail.com | 2yr | $27k |
| 19 | Gabriela Rodrigues Murillo | rodriguesmurillogabriela@gmail.com | 3yr | $34k |

All 16 have `cookie_status: "pending"` — cookies must be injected before use.
All have `resume_path: null` — resumes not yet assigned locally.

### Stonewalled (flagged by Indeed — do not use)

| Slot | Name | Email | Stonewalled |
|------|------|-------|-------------|
| 9 | Oswaldin Lara | oswaldin.lara@gmail.com | 2026-03-14 |
| 10 | Abraham Ibarra Padilla | abrahamibarrapadilla297@gmail.com | 2026-03-14 |
| 18 | Maria Conchita | mconchita521@gmail.com | 2026-03-14 |

All three hit on the same day — likely a batch-run that triggered mass flagging.

## Phone Numbers (for SmartApply forms)

| Email | Phone |
|-------|-------|
| oswaldin.lara@gmail.com | +12068819903 |
| others | — (add as SmartApply requests them) |
