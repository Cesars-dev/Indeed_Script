# P8 Final Submit — MASTER PLAN

> Source: audit + action_plan + cross_reference (all verified against live code)
> Status: **READY TO EXECUTE** — zero open items
> Date: 2026-03-14 Session 7

---

## Execution Order

### Step 1: `handlers.py` — Add modal dismiss handler + harden error guard

**File:** `src/smartapply/handlers.py`

**1a. Add `handle_modal_dismiss()` — insert BEFORE line 17 (after imports, before handler 1)**

New function with early-exit guard: check for `[role="dialog"]` first, skip entirely if no dialog visible.

**1b. Fix error guard on line 240 — filter false-positive errors**

Replace `has_errors = len(dom["errors"]) > 0` with filtered version.

### Step 2: `dom_scanner.py` — Add modal + reCAPTCHA detection

**File:** `src/smartapply/dom_scanner.py`

After line 101 (checkboxes), add:
- Modal detection: `[role="dialog"], [aria-modal="true"]`
- reCAPTCHA detection: `iframe[src*="recaptcha"]`

### Step 3: `playwright_indeed.py` — Add `_has_recaptcha()` and `_solve_recaptcha()`

**File:** `src/playwright_indeed.py`

After `_solve_cf()` (~line 916), add both functions.

### Step 4: `router.py` — Wire everything together

**File:** `src/smartapply/router.py`

- Import modal handler (line 17-25)
- Add to handler chain (line 32-40)
- Add reCAPTCHA check before deterministic handlers (line ~110)

### Step 5: Verify — syntax check all changed files

```bash
python3.13 -c "import py_compile; py_compile.compile('src/smartapply/handlers.py', doraise=True)"
python3.13 -c "import py_compile; py_compile.compile('src/smartapply/dom_scanner.py', doraise=True)"
python3.13 -c "import py_compile; py_compile.compile('src/smartapply/router.py', doraise=True)"
python3.13 -c "import py_compile; py_compile.compile('src/playwright_indeed.py', doraise=True)"
```

---

## Open Items: NONE

All gaps from cross-reference resolved:
- Gap 1 (reCAPTCHA image challenge): Accepted — fail gracefully, not worth solving now
- Gap 2 (response verification): Improved — check response token + re-screenshot
- Gap 3 (handler ordering): Fixed — early-exit dialog check
- Gap 4 (private imports): No issue — matches existing pattern
