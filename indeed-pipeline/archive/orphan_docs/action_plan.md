# Action Plan — Indeed Auto-Apply Pipeline
> Created: 2026-03-05 | Based on: code audit + Supabase query
> Single source of truth for what to fix and in what order.

---

## Current Reality (audited)

**Only working profile:** `k19td50a` (oswaldin.lara@gmail.com)
- `cookie_status = active` ✅
- `stone_walled = TRUE` 🔴 — CF-fatigued from 9 prior attempts
- `phone_number = +12068819903` ✅
- `resume_path = NULL` — falls back to `resume_oswaldo.pdf`

**Root cause of all failed applies:** 180s `asyncio.wait_for` timeout kills the Gemini loop at step 22 before the questions module completes. Confirmed by 2 entries in `test_run_logs`.

---

## Fix Order

### 🔴 FIX 1 — Remove the 180s timeout cap
**File:** `src/playwright_indeed.py`

**What:** `_gemini_loop()` wraps `_gemini_loop_inner()` in `asyncio.wait_for(..., timeout=180)`. Remove the wrapper — let the loop run to natural completion.

**Also in the same pass:**
- Change `range(35)` → `range(50)` in `_gemini_loop_inner`
- Update prompt display from `{step}/35` → `{step}/50`
- Add exit when `consecutive_failures >= 10` (currently only scrolls at 3, never exits)

**Test:** Run `batch_test.py` against a fresh viewjob URL. Check `/tmp/playwright_debug/` — should see steps past 22 and either a success screen or a real failure reason.

---

### 🔴 FIX 2 — Stone-walled check + CF tracking
**File:** `src/playwright_indeed.py` — top of `apply_to_job()`

**What to add before starting the profile:**
1. GET `adspower_profiles` row for `user_id`
2. If `stone_walled = true` AND `stone_walled_at` < 24h ago → return `{"status": "skipped", "reason": "stone_walled"}`
3. If `stone_walled = true` AND `stone_walled_at` >= 24h ago → PATCH `stone_walled=false, stone_walled_at=null` then proceed

**What to add when CF is detected** (currently returns skipped with no DB update):
- PATCH `adspower_profiles`: `stone_walled=true`, `stone_walled_at=now`, `cf_hits+1`, `last_cf_hit=now`, `risk_level='hot'`

**Immediate action before testing:** Manually reset `k19td50a` in Supabase:
```sql
UPDATE adspower_profiles SET stone_walled = false, stone_walled_at = null WHERE user_id = 'k19td50a';
```
(Only do this after the profile has rested 24h+ from last CF hit.)

---

### 🔴 FIX 3 — Per-profile data from Supabase (replace hardcoded dict)
**File:** `src/playwright_indeed.py`

**What:** At module load, fetch all rows from `adspower_profiles`. Cache as `dict[user_id → row]`. Delete `PROFILE_DATA` dict and all `APPLICANT_*` env var constants.

**DB already has:** `full_name`, `email`, `phone_number`, `years_exp`, `education`, `salary_hr`, `salary_yr`, `resume_path`

**In `_gemini_decide()`:**
- `name` → `profile["full_name"]` (column is `full_name`, not `name`)
- `phone` → `profile["phone_number"]`
- `salary_hr` / `salary_yr` → from profile row
- Resume: use `profile["resume_path"]` if set, else fall back to `resume_oswaldo.pdf`

**Blocker this fixes:** Currently `APPLICANT_NAME` is "Oswaldo Lara" for ALL 19 profiles. All other profiles have no phone number in code.

---

### 🔴 FIX 4 — Wire execution logging
**File:** `src/supabase_client.py`

Add `log_execution(data: dict)` — INSERTs one row into the `executions` table. Schema confirmed in DB (see seeded rows: `run_id`, `profile_id`, `job_id`, `status`, `steps`, `elapsed_s`, `form_reached`, `questions_reached`, `submission_reached`, `cf_detected`, etc.)

**File:** `src/playwright_indeed.py`
- Generate `run_id = str(uuid.uuid4())` once at batch start
- Call `log_execution()` after every `apply_to_job()` call (all outcomes)
- PATCH `adspower_profiles` after each apply:
  - success/failed → increment `applies_total`, set `last_used=now`
  - cf_block → handled by Fix 2 above
  - skipped → no update needed

**Also audit:** `is_job_applied()` and `upsert_applied_job()` in `supabase_client.py` are still used by `apply_runner.py`. Keep them unless `applied_jobs` table is being retired.

---

### 🟡 FIX 5 — Add 9 new profiles to `apply_runner.py`
**File:** `src/apply_runner.py`

`PROFILE_IDS` list has 10 entries. DB has 19 profiles. Add the 9 missing user IDs:

```
k1a2vu6e  abrahamibarrapadilla297@gmail.com
k1a2vul9  alejandralizzete@gmail.com
k1a2vun1  angelivanlopez72@gmail.com
k1a2vuna  ellukistrike@gmail.com
k1a2vuni  erickssson528@gmail.com
k1a2vuno  fmgutierrez123@gmail.com
k1a2vuny  jonathanjonadidi@gmail.com
k1a2vuom  limonrangel308@gmail.com
k1a2vuov  mconchita521@gmail.com
k1a2vupc  rodriguesmurillogabriela@gmail.com  ← (19th — not in first query result, verify)
```

(Only matters for profiles that have active sessions — wire them in now so they're ready.)

---

### 🟡 FIX 6 — `batch_test.py` stdin URL input
**File:** `scripts/batch_test.py`

Current hardcoded `URLS` list has expired Indeed job tokens. Replace with stdin input:
```
Enter job URLs to test (one per line, blank line to finish):
```

---

### ⚙️ MANUAL TASKS (require human hands — cannot be automated)

These cannot be scripted. Do 1–2 profiles per day.

**Per profile (18 profiles still need this):**
1. Open AdsPower → launch that profile's browser
2. `gmail.com` → log in with that profile's Gmail
3. `indeed.com` → Sign In with Gmail → confirm logged in
4. Find any receptionist/office job → click Easy Apply → complete one-time profile wizard (name, phone, resume) → close
5. Set `cookie_status = 'active'` in Supabase for that `user_id`

**Phone numbers needed:** 18/19 profiles have `phone_number = NULL` in DB. Add real phone numbers to `adspower_profiles` before running those profiles through the apply engine.

---

## Phone Numbers Needed (fill in Supabase)

| user_id | email | phone |
|---------|-------|-------|
| k19td4st | gabrielalopezgomez80@gmail.com | ??? |
| k19td4tu | alexeishon2@gmail.com | ??? |
| k19td4uh | garciaramosjonathan8@gmail.com | ??? |
| k19td4v5 | yoshiporfirioyoshio@gmail.com | ??? |
| k19td4vp | gutierrezramirezhectormanuel6@gmail.com | ??? |
| k19td4wc | martinezmedinajonathan975@gmail.com | ??? |
| k19td4x8 | clarasanchezvillela@gmail.com | ??? |
| k19td4xs | alisfleet@gmail.com | ??? |
| k1a2vu6e | abrahamibarrapadilla297@gmail.com | ??? |
| k1a2vul9 | alejandralizzete@gmail.com | ??? |
| k1a2vun1 | angelivanlopez72@gmail.com | ??? |
| k1a2vuna | ellukistrike@gmail.com | ??? |
| k1a2vuni | erickssson528@gmail.com | ??? |
| k1a2vuno | fmgutierrez123@gmail.com | ??? |
| k1a2vuny  | jonathanjonadidi@gmail.com | ??? |
| k1a2vuom | limonrangel308@gmail.com | ??? |
| k1a2vuov | mconchita521@gmail.com | ??? |
| k1a2vupc | rodriguesmurillogabriela@gmail.com | ??? |

---

## First Real Test (after Fix 1 + Fix 2 + reset stone_walled)

```bash
# 1. Reset k19td50a in Supabase (after 24h rest):
#    UPDATE adspower_profiles SET stone_walled=false, stone_walled_at=null WHERE user_id='k19td50a';

# 2. Run batch test with a fresh job URL:
cd indeed-pipeline
PYTHONUNBUFFERED=1 PYTHONPATH=venv_local/lib/python3.13/site-packages python3.13 -u scripts/batch_test.py

# 3. Review screenshots:
open /tmp/playwright_debug/
```

**Success criteria:**
- Steps go past 22
- See a submission screen OR a meaningful failure reason (not "Timed out")
- `test_run_logs` shows `submission_reached = true`

---

## Summary Table

| # | Fix | File(s) | Effort | Status |
|---|-----|---------|--------|--------|
| 1 | Remove 180s timeout, set 50 steps, exit at 10 consecutive failures | `playwright_indeed.py` | 10 min | ✅ |
| 2 | Stone-walled check + CF PATCH | `playwright_indeed.py` | 20 min | ✅ |
| 3 | Per-profile data from Supabase, delete hardcoded dict | `playwright_indeed.py` | 30 min | ✅ |
| 4 | `log_execution()` + wire it after every apply | `supabase_client.py`, `playwright_indeed.py` | 30 min | ✅ |
| 5 | Add 9 missing profiles to PROFILE_IDS | `apply_runner.py` | 5 min | ✅ |
| 6 | stdin URL input for batch_test.py | `batch_test.py` | 10 min | ✅ |
| M1 | Phone numbers — fill in Supabase for 18 profiles | Supabase (manual) | — | ❌ |
| M2 | Activate sessions — 18 profiles need Indeed login + wizard | AdsPower (manual) | 1-2/day | ❌ |
