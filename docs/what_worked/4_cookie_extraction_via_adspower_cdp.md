# Cookie Extraction via AdsPower CDP

## Approach That Works
Use AdsPower's browser profile via WebSocket CDP connection, navigate to Indeed, extract auth cookies.

## Script Location
`antigravity-workspace-template/scripts/export_cookies.py`

## Key Cookies to Extract
| Cookie | Purpose |
|--------|---------|
| `CTK` | Indeed session token |
| `indeed_sess` | Main auth session |
| `INDEED_CSRF_TOKEN` | CSRF protection |
| `LC` | Locale/region |

## Flow
1. Start AdsPower profile via API: `POST /api/v1/browser/start?user_id={id}`
2. Get WebSocket debug URL from response
3. Connect Playwright to that WS URL
4. Navigate to `https://www.indeed.com` (already logged in from profile)
5. Extract cookies → save to `config/cookies/account_{n}.json`
6. Stop profile: `GET /api/v1/browser/stop?user_id={id}`

## Run Command
```bash
python3 -u scripts/export_cookies.py
```
(The `-u` flag is critical — forces unbuffered stdout so you see logs in real time)

## Validity
Cookies last weeks. Rerun script when jobs start failing with "Not logged in" reason in Supabase.

## Notes
- Run from Mac (AdsPower runs locally)
- Cool down 15-25s between accounts to avoid rate limits
- Google OAuth popup is handled by `context.expect_page()` in Playwright
