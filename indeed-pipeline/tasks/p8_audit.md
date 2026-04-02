# P8 Audit — Session 8 Post-Surgery

## What Was Cut (Changes Made)

| File | Change | Lines | Verified |
|------|--------|-------|----------|
| `dom_scanner.py` | DOM tree climbing for radio question text | +15 | ✅ Tested — extracts "authorized to work" and "reliably commute" |
| `dom_scanner.py` | Modal detection (`[role="dialog"]`) + reCAPTCHA flag | +18 | ✅ Tested |
| `handlers.py` | `handle_modal_dismiss()` — new handler | +25 | ✅ Wired into handler chain |
| `handlers.py` | Error guard hardening — filters reCAPTCHA/privacy false positives | +8 | ✅ Tested |
| `recaptcha.py` | **NEW FILE** — 2Captcha token injection solver | +165 | ✅ Tested — solved in 67s, accepted |
| `router.py` | reCAPTCHA pre-check → 2Captcha → click Submit after solve | +20 | ✅ Tested — no re-solve loop |
| `router.py` | `recaptcha_solved` flag prevents infinite re-solve | +1 | ✅ Tested |
| `router.py` | `post-apply` URL = success signal | +1 | ✅ Correct — post-apply is confirmation page |
| `router.py` | Continue-after-Flash/Pro action on same URL | +12 | ✅ Tested |
| `router.py` | Modal handler wired first in chain | +1 | ✅ Tested |
| `playwright_indeed.py` | `_has_recaptcha()` + `_solve_recaptcha()` (old Bezier) | +40 | ⚠️ Superseded by `recaptcha.py` — dead code |
| `batch_test.py` | Test URL changed to Receptionist job | +3 | ✅ |
| `memory.md` | Session 8 documentation | +50 | ✅ |
| `NEXT_STEPS.md` | Updated pipeline stages + priorities | +15 | ✅ |

## What's Confirmed Working (Test Evidence)

```
step 00: profile-location    → ✓ Continue (deterministic)
step 01: resume-selection    → ✓ Upload resume (deterministic)
step 02: resume-selection    → ✓ Continue (deterministic)
step 03: privacy-settings    → ✓ Continue (deterministic)
step 04: questions/1         → ✓ Continue (deterministic — cookies had answers)
step 05: review-module       → 🔐 reCAPTCHA → Solved 67s → ✓ Submit clicked
step 06: post-apply          → 🎉 APPLICATION SUBMITTED
```

## What's NOT Done (Pending Tasks)

### P8.1 — `apply_patterns` table (Learning Loop)
- **Status**: Infrastructure exists (`load_dynamic_patterns()`, `get_dynamic_answer()` in `patterns.py`) but table doesn't exist in Supabase
- **What's needed**:
  1. CREATE TABLE `apply_patterns` in Supabase (1 migration)
  2. After Gemini answers a question → INSERT into `apply_patterns` (~10 lines in router.py)
  3. Before calling Gemini → check `apply_patterns` (~5 lines in handlers.py)
- **Impact**: Every Gemini answer makes deterministic layer permanently smarter
- **Priority**: Medium — system works without it, just costs more Gemini API calls

### P8.2 — Review Page Skip List
- **Status**: Flash wastes shots trying to check marketing checkboxes
- **What's needed**: Add to deterministic handler skip list:
  - "Get email updates" → SKIP
  - "Receive calls or text" → SKIP  
  - "Take survey" → SKIP
- **Impact**: Saves 3-4 Flash shots per application on review page
- **Priority**: Low — doesn't block submissions

### P8.3 — Dead Code Cleanup
- **Status**: `_has_recaptcha()` and `_solve_recaptcha()` in `playwright_indeed.py` are now dead code (replaced by `recaptcha.py`)
- **What's needed**: Remove old functions
- **Priority**: Low — cosmetic

### P8.4 — Stress Test Across Jobs
- **Status**: Only tested with 1 job (Receptionist, Duluth MN)
- **What's needed**: Run pipeline against 5-10 different jobs with varying question counts
- **APPLY_TESTS.md** has test URLs ready
- **Priority**: High — must validate pattern coverage before production

### P5 — Session Activation (Manual)
- **Status**: Not started
- **What's needed**: Log into Gmail + Indeed per AdsPower profile (1-2/day manually)
- **Priority**: Required for production

### P6 — Search Page Warmup
- **Status**: Not started
- **What's needed**: Navigate to `indeed.com/jobs?q=...&l=...` before job URL
- **Priority**: Medium — reduces bot detection risk

## Risks

1. **2Captcha solve time**: 67-112s is slow. At 300 apps/day, reCAPTCHA adds ~8 hours of wait time total. Consider CapSolver ($0.80/1k, 3-9s) if speed becomes bottleneck.
2. **Pattern coverage**: 50+ hardcoded patterns cover common questions but job-specific certs (HVAC, nursing, etc.) will need Gemini. The learning loop (P8.1) mitigates this over time.
3. **Same job repeated**: We hit the Receptionist job ~8 times with Conchita. Indeed may flag. Use different profiles and jobs going forward.
