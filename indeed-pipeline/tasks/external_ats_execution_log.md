# External ATS — DOE Execution Log

> **Branch:** `feature/external-ats-apply` (Branch C)  
> **Started:** 2026-03-17 21:04  
> **Goal:** Make external ATS apply work end-to-end

---

## Iteration 1 — 2026-03-17 21:01

### What happened
- Pipeline ran, AdsPower restarted OK (90s wait worked)
- CDP connected first attempt on all profiles ✅
- Job 1 (`jk=00c0f8ad1b82c124`): Profile k1a2vu6e timed out on `indeed.com` warmup (30s). Proxy slow.
- Job 1 retry: Profile k19td50a — page loaded, no apply button, no external button → skipped
- Job 2 (`jk=2a599bdfcae3f4ef`): Profile k19td50a — **External ATS detected! Clicked through!** 🎯
- **CRASH:** `_screenshot()` raised `CancelledError` on CDP `Page.captureScreenshot` during pre-click screenshot. The outer `try/except` caught it, which aborted the ENTIRE external handler flow instead of just the screenshot.

### Root cause
`_screenshot()` raises exceptions. The external handler click + screenshot was inside a single `try/except` block — any failure (including non-critical screenshot) would abort everything and fall through to "no apply button found".

### Fix applied
Restructured the external ATS block:
- Split button detection (try/except) from handler execution (no try/except wrapping)
- Wrapped both screenshots in individual `try/except` with "non-fatal" print
- Handler now always runs once button is found, regardless of screenshot failures
- **Committed:** `fd27bc8`

### Directive update
- Screenshot failures on Indeed's viewjob page are common (CDP session conflicts when page is mid-load)
- All screenshots in flow paths should ALWAYS be wrapped in try/except — never let them crash the pipeline

---

## Iteration 2 — 2026-03-17 21:04

### Changes before run
1. Modified `batch_test.py` to:
   - Skip URLs already attempted in `test_run_logs` (query Supabase at startup)
   - Resume from next profile after last used (don't repeat profiles on same URLs)
   - Reduce AdsPower wait from 90s to 60s (it came up in ~45s last time)

### Run in progress...
