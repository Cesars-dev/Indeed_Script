# External ATS — Action Plan

## Pre-requisite: Database Migration

Run these SQL statements FIRST (safe — adding nullable columns only):

```sql
-- apply_step_log: add tracking columns
ALTER TABLE apply_step_log ADD COLUMN IF NOT EXISTS profile_id text;
ALTER TABLE apply_step_log ADD COLUMN IF NOT EXISTS job_url text;
ALTER TABLE apply_step_log ADD COLUMN IF NOT EXISTS ats_domain text;

-- apply_patterns: add ATS segmentation
ALTER TABLE apply_patterns ADD COLUMN IF NOT EXISTS ats_domain text;

-- apply_runs: add tracking columns
ALTER TABLE apply_runs ADD COLUMN IF NOT EXISTS profile_id text;
ALTER TABLE apply_runs ADD COLUMN IF NOT EXISTS job_url text;
ALTER TABLE apply_runs ADD COLUMN IF NOT EXISTS ats_domain text;
```

---

## Change 1: CREATE `src/smartapply/external_ats.py`

New file. ~150 lines. Same interface as `apply_smartapply()`.

```python
"""
External ATS Apply — handles Workday / Greenhouse / Lever / etc.
Budget: 5 Flash + 3 Pro = 8 Gemini calls max.
"""
import asyncio, json, os, random, time
from urllib.parse import urlparse
from .gemini_fallback import gemini_decide
from .logger import log


async def external_ats_apply(
    page, docx_path: str | None, profile: dict, debug_dir: str,
    job_url: str = "", profile_id: str = "",
) -> dict:
    from src.playwright_indeed import _screenshot, _execute, human_scroll

    ats_domain = urlparse(page.url).netloc.replace("www.", "")
    t0 = time.time()
    flash_calls = 0
    pro_calls = 0
    MAX_FLASH = 5
    MAX_PRO = 3

    print(f"  🌐 External ATS: {ats_domain}")

    for step in range(MAX_FLASH + MAX_PRO):
        url = page.url
        print(f"\n  ── ext step {step:02d} ── {url[:90]}")

        # ── DOM scan ──
        from .dom_scanner import scan_dom
        try:
            dom = await scan_dom(page)
        except Exception as e:
            print(f"  ⚠️ DOM scan failed: {e}")
            await asyncio.sleep(1)
            continue

        # ── Success detection (external-aware) ──
        body = await page.evaluate("() => document.body.innerText.substring(0, 2000)")
        body_lower = body.lower()
        SUCCESS_SIGNALS = [
            "application submitted", "application complete",
            "thank you for your application", "your application has been received",
            "application was submitted", "you applied", "successfully submitted",
            "thank you for applying", "application received",
        ]
        if any(s in body_lower for s in SUCCESS_SIGNALS):
            _log_step(step, url, "signal", True, {"action": "done"}, ats_domain, job_url, profile_id)
            _log_run("success", "External ATS: application submitted", step, flash_calls, pro_calls, t0, ats_domain, url, debug_dir, job_url, profile_id)
            return {"status": "success", "reason": f"Application submitted on {ats_domain}"}

        # ── Fail-fast: login wall / account creation ──
        FAIL_SIGNALS = [
            "sign in to continue", "create an account", "log in to apply",
            "sign up to apply", "create your account", "register to apply",
        ]
        if any(s in body_lower for s in FAIL_SIGNALS):
            _log_step(step, url, "fail_fast", False, {"action": "failed", "reason": "login wall"}, ats_domain, job_url, profile_id)
            _log_run("failed", f"External ATS: login wall on {ats_domain}", step, flash_calls, pro_calls, t0, ats_domain, url, debug_dir, job_url, profile_id)
            return {"status": "failed", "reason": f"Login wall on {ats_domain}"}

        # ── Screenshot + Gemini decision ──
        use_pro = flash_calls >= MAX_FLASH
        tier = "external_pro" if use_pro else "external_flash"

        if use_pro and pro_calls >= MAX_PRO:
            break  # exhausted

        try:
            ss_name = f"step_{step:02d}_full" if use_pro else f"step_{step:02d}"
            screenshot = await _screenshot(page, debug_dir, ss_name, full_page=use_pro)
        except Exception as e:
            print(f"  ⚠️ Screenshot failed: {e}")
            continue

        try:
            action = await gemini_decide(screenshot, dom, profile, use_pro=use_pro)
        except Exception as e:
            print(f"  ⚠️ Gemini error: {e}")
            continue

        if use_pro:
            pro_calls += 1
        else:
            flash_calls += 1

        act = action.get("action", "")
        print(f"  🤖 {tier} → {json.dumps(action)[:120]}")

        if act == "done":
            _log_step(step, url, tier, True, action, ats_domain, job_url, profile_id)
            _log_run("success", action.get("reason", "Gemini confirmed"), step, flash_calls, pro_calls, t0, ats_domain, url, debug_dir, job_url, profile_id)
            return {"status": "success", "reason": action.get("reason", f"Submitted on {ats_domain}")}

        if act == "failed":
            _log_step(step, url, tier, False, action, ats_domain, job_url, profile_id)
            _log_run("failed", action.get("reason", "Gemini: unrecoverable"), step, flash_calls, pro_calls, t0, ats_domain, url, debug_dir, job_url, profile_id)
            return {"status": "failed", "reason": action.get("reason", f"Stuck on {ats_domain}")}

        if act == "skip":
            _log_step(step, url, tier, False, action, ats_domain, job_url, profile_id)
            _log_run("skipped", action.get("reason", "Gemini: skip"), step, flash_calls, pro_calls, t0, ats_domain, url, debug_dir, job_url, profile_id)
            return {"status": "skipped", "reason": action.get("reason", "External: not applicable")}

        # ── Execute action ──
        ok = await _execute(page, action, docx_path)
        _log_step(step, url, tier, ok, action, ats_domain, job_url, profile_id)

        # ── Pattern learning ──
        if ok and action.get("target"):
            log("apply_patterns", {
                "question_text": action.get("target", "")[:500],
                "answer_value": str(action.get("value") or action.get("target", ""))[:200],
                "answer_type": f"external_{act}",
                "source": tier,
                "ats_domain": ats_domain,
            })

        if not ok:
            print(f"  ↓ Action failed")
            await human_scroll(page, 200)

        await asyncio.sleep(random.uniform(1.0, 2.5))

    # ── Exhausted ──
    _log_run("failed", f"External ATS: {MAX_FLASH + MAX_PRO} calls exhausted on {ats_domain}", MAX_FLASH + MAX_PRO, flash_calls, pro_calls, t0, ats_domain, page.url, debug_dir, job_url, profile_id)
    return {"status": "failed", "reason": f"Exhausted {MAX_FLASH + MAX_PRO} Gemini calls on {ats_domain}"}


# ── Logging helpers ──────────────────────────────────────────────────────────

def _log_step(step, url, tier, success, action, ats_domain, job_url, profile_id):
    log("apply_step_log", {
        "step_num": step, "url": url, "tier": tier,
        "success": success, "action": action,
        "ats_domain": ats_domain, "job_url": job_url, "profile_id": profile_id,
    })

def _log_run(status, reason, steps, flash, pro, t0, ats_domain, last_url, debug_dir, job_url, profile_id):
    log("apply_runs", {
        "status": status, "reason": reason,
        "total_steps": steps, "flash_steps": flash, "pro_steps": pro,
        "deterministic_steps": 0, "failed_steps": 0,
        "elapsed_s": round(time.time() - t0, 1),
        "ats_domain": ats_domain, "last_url": last_url,
        "debug_dir": debug_dir, "job_url": job_url, "profile_id": profile_id,
    })
```

---

## Change 2: MODIFY `src/playwright_indeed.py` (lines 1330-1340)

Replace the skip with external ATS routing:

```python
# BEFORE (line 1330-1340):
if not apply_btn:
    try:
        await page.get_by_text("Apply on company site", exact=False).first.wait_for(
            state="visible", timeout=2000
        )
        return {"status": "skipped", "reason": "External apply — company ATS"}
    except Exception:
        pass
    title = await page.title()
    return {"status": "skipped", "reason": f"No apply button found (page: {title[:60]})"}

# AFTER:
if not apply_btn:
    try:
        ext_btn = page.get_by_text("Apply on company site", exact=False).first
        await ext_btn.wait_for(state="visible", timeout=2000)
        # External ATS — click and handle instead of skipping
        await _screenshot(page, debug_dir, "00_external_pre_click")
        await ext_btn.scroll_into_view_if_needed()
        await _delay(1.0, 2.0)
        await ext_btn.click()
        await _delay(3.0, 5.0)
        # Handle new tab (Indeed usually opens external in new tab)
        pages = page.context.pages
        if len(pages) > 1:
            page = pages[-1]
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
        await _screenshot(page, debug_dir, "01_external_land")
        from src.smartapply.external_ats import external_ats_apply
        return await external_ats_apply(
            page, docx_path, profile, debug_dir,
            job_url=apply_url, profile_id=user_id,
        )
    except Exception:
        pass
    title = await page.title()
    return {"status": "skipped", "reason": f"No apply button found (page: {title[:60]})"}
```

---

## Change 3: MODIFY `src/smartapply/gemini_fallback.py` — add external prompt

Add external ATS guidance to `build_targeted_prompt()`:

```python
# In build_targeted_prompt(), after the profile summary (line 64-70), add:
if profile.get("is_external"):
    parts.append("""
EXTERNAL ATS RULES:
- This is a company career site (Workday, Greenhouse, Lever, etc.), NOT Indeed
- If you see "Sign in" / "Create account" / "Log in to apply" → return failed
- If you see CAPTCHA → return failed
- Look for "Apply" / "Submit Application" / "Apply for this Job" buttons
- Upload resume when a file input appears (use upload action)
- Fill name, email, phone when fields appear
- Do NOT try to register or create an account
""")
```

---

## Change 4: MODIFY `src/smartapply/__init__.py`

```python
# BEFORE:
from .router import apply_smartapply
__all__ = ["apply_smartapply"]

# AFTER:
from .router import apply_smartapply
from .external_ats import external_ats_apply
__all__ = ["apply_smartapply", "external_ats_apply"]
```

---

## Change 5: MODIFY `src/smartapply/dom_scanner.py` (line 137-140)

Add external ATS success signals:

```python
# BEFORE:
result.success = bodyText.includes('Application submitted')
    || bodyText.includes('application was submitted')
    || bodyText.includes('You applied');

# AFTER:
result.success = bodyText.includes('Application submitted')
    || bodyText.includes('application was submitted')
    || bodyText.includes('You applied')
    || bodyText.includes('Thank you for your application')
    || bodyText.includes('Your application has been received')
    || bodyText.includes('Application Complete')
    || bodyText.includes('Thank you for applying')
    || bodyText.includes('Successfully submitted');
```

---

## Execution Order

1. Run SQL migration (add columns)
2. Create `src/smartapply/external_ats.py` (Change 1)
3. Modify `src/smartapply/__init__.py` (Change 4)
4. Modify `src/smartapply/gemini_fallback.py` (Change 3)
5. Modify `src/smartapply/dom_scanner.py` (Change 5)
6. Modify `src/playwright_indeed.py` (Change 2) — last, since it depends on 1-4
7. Test with a known external ATS job URL
