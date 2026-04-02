"""
External ATS Apply — handles Workday / Greenhouse / Lever / etc.
Budget: 5 Flash + 3 Pro = 8 Gemini calls max.

Same interface as apply_smartapply():
  result = await external_ats_apply(page, docx_path, profile, debug_dir, ...)
  # result = {"status": "success"|"failed"|"skipped", "reason": "..."}
"""
import asyncio
import json
import os
import random
import time
from urllib.parse import urlparse

from .gemini_fallback import gemini_decide
from .logger import log


# ── Success / fail-fast signals for external ATS pages ────────────────────────
_SUCCESS_SIGNALS = [
    "application submitted", "application complete",
    "thank you for your application", "your application has been received",
    "application was submitted", "you applied", "successfully submitted",
    "thank you for applying", "application received",
]

_FAIL_SIGNALS = [
    "sign in to continue", "create an account", "log in to apply",
    "sign up to apply", "create your account", "register to apply",
    "login to apply", "sign in to apply",
]


async def external_ats_apply(
    page,
    docx_path: str | None,
    profile: dict,
    debug_dir: str,
    job_url: str = "",
    profile_id: str = "",
) -> dict:
    """
    Navigate an external ATS form using Gemini Vision.
    Budget: 5 Flash calls + 3 Pro calls = 8 max.
    """
    # Import from main module (avoid circular at module level)
    from src.playwright_indeed import _screenshot, _execute, human_scroll

    ats_domain = urlparse(page.url).netloc.replace("www.", "")
    t0 = time.time()
    flash_calls = 0
    pro_calls = 0
    MAX_FLASH = 5
    MAX_PRO = 3
    MAX_STEPS = MAX_FLASH + MAX_PRO

    print(f"  🌐 External ATS: {ats_domain}")

    for step in range(MAX_STEPS):
        url = page.url
        print(f"\n  ── ext step {step:02d} ── {url[:90]}")

        # ── DOM scan ──────────────────────────────────────────────────────────
        from .dom_scanner import scan_dom
        try:
            dom = await scan_dom(page)
        except Exception as e:
            print(f"  ⚠️ DOM scan failed: {e}")
            await asyncio.sleep(1)
            continue

        # ── Success detection (external-aware) ────────────────────────────────
        try:
            body = await page.evaluate(
                "() => document.body.innerText.substring(0, 2000)"
            )
            body_lower = body.lower()
        except Exception:
            body_lower = ""

        if dom.get("success") or any(s in body_lower for s in _SUCCESS_SIGNALS):
            _log_step(step, url, "signal", True,
                      {"action": "done"}, ats_domain, job_url, profile_id)
            _log_run("success", f"External ATS: submitted on {ats_domain}",
                     step, flash_calls, pro_calls, t0,
                     ats_domain, url, debug_dir, job_url, profile_id)
            return {
                "status": "success",
                "reason": f"Application submitted on {ats_domain}",
            }

        # ── Fail-fast: login wall / account creation ──────────────────────────
        if any(s in body_lower for s in _FAIL_SIGNALS):
            _log_step(step, url, "fail_fast", False,
                      {"action": "failed", "reason": "login wall"},
                      ats_domain, job_url, profile_id)
            _log_run("failed", f"External ATS: login wall on {ats_domain}",
                     step, flash_calls, pro_calls, t0,
                     ats_domain, url, debug_dir, job_url, profile_id)
            return {
                "status": "failed",
                "reason": f"Login wall on {ats_domain}",
            }

        # ── Decide tier: Flash first, then Pro ────────────────────────────────
        use_pro = flash_calls >= MAX_FLASH
        tier = "external_pro" if use_pro else "external_flash"

        if use_pro and pro_calls >= MAX_PRO:
            break  # exhausted all calls

        # ── Screenshot ────────────────────────────────────────────────────────
        try:
            ss_name = f"step_{step:02d}_full" if use_pro else f"step_{step:02d}"
            screenshot = await _screenshot(
                page, debug_dir, ss_name, full_page=use_pro
            )
        except Exception as e:
            print(f"  ⚠️ Screenshot failed: {e}")
            continue

        # ── Gemini decision ───────────────────────────────────────────────────
        try:
            action = await gemini_decide(
                screenshot, dom, profile, use_pro=use_pro
            )
        except Exception as e:
            print(f"  ⚠️ Gemini error: {e}")
            if use_pro:
                pro_calls += 1
            else:
                flash_calls += 1
            continue

        if use_pro:
            pro_calls += 1
        else:
            flash_calls += 1

        act = action.get("action", "")
        print(f"  🤖 {tier} → {json.dumps(action)[:120]}")

        # ── Terminal actions ──────────────────────────────────────────────────
        if act == "done":
            _log_step(step, url, tier, True, action,
                      ats_domain, job_url, profile_id)
            _log_run("success", action.get("reason", f"Submitted on {ats_domain}"),
                     step, flash_calls, pro_calls, t0,
                     ats_domain, url, debug_dir, job_url, profile_id)
            return {
                "status": "success",
                "reason": action.get("reason", f"Submitted on {ats_domain}"),
            }

        if act == "failed":
            _log_step(step, url, tier, False, action,
                      ats_domain, job_url, profile_id)
            _log_run("failed", action.get("reason", f"Stuck on {ats_domain}"),
                     step, flash_calls, pro_calls, t0,
                     ats_domain, url, debug_dir, job_url, profile_id)
            return {
                "status": "failed",
                "reason": action.get("reason", f"Stuck on {ats_domain}"),
            }

        if act == "skip":
            _log_step(step, url, tier, False, action,
                      ats_domain, job_url, profile_id)
            _log_run("skipped", action.get("reason", "External: not applicable"),
                     step, flash_calls, pro_calls, t0,
                     ats_domain, url, debug_dir, job_url, profile_id)
            return {
                "status": "skipped",
                "reason": action.get("reason", "External: not applicable"),
            }

        # ── Execute action ────────────────────────────────────────────────────
        ok = await _execute(page, action, docx_path)
        _log_step(step, url, tier, ok, action,
                  ats_domain, job_url, profile_id)

        # ── Pattern learning ──────────────────────────────────────────────────
        if ok and action.get("target"):
            log("apply_patterns", {
                "question_text": action.get("target", "")[:500],
                "answer_value": str(
                    action.get("value") or action.get("target", "")
                )[:200],
                "answer_type": f"external_{act}",
                "source": tier,
                "ats_domain": ats_domain,
            })

        if not ok:
            print(f"  ↓ Action failed")
            await human_scroll(page, 200)

        await asyncio.sleep(random.uniform(1.0, 2.5))

    # ── All calls exhausted ───────────────────────────────────────────────────
    _log_run(
        "failed",
        f"External ATS: {MAX_STEPS} calls exhausted on {ats_domain}",
        MAX_STEPS, flash_calls, pro_calls, t0,
        ats_domain, page.url, debug_dir, job_url, profile_id,
    )
    return {
        "status": "failed",
        "reason": f"Exhausted {MAX_STEPS} Gemini calls on {ats_domain}",
    }


# ── Logging helpers ───────────────────────────────────────────────────────────

def _log_step(step, url, tier, success, action, ats_domain, job_url, profile_id):
    log("apply_step_log", {
        "step_num": step,
        "url": url[:500],
        "tier": tier,
        "success": success,
        "action": action,
        "ats_domain": ats_domain,
        "job_url": job_url[:500] if job_url else "",
        "profile_id": profile_id,
    })


def _log_run(status, reason, steps, flash, pro, t0,
             ats_domain, last_url, debug_dir, job_url, profile_id):
    log("apply_runs", {
        "status": status,
        "reason": reason[:500],
        "total_steps": steps,
        "flash_steps": flash,
        "pro_steps": pro,
        "deterministic_steps": 0,
        "failed_steps": 0,
        "elapsed_s": round(time.time() - t0, 1),
        "ats_domain": ats_domain,
        "last_url": last_url[:500],
        "debug_dir": debug_dir,
        "job_url": job_url[:500] if job_url else "",
        "profile_id": profile_id,
    })
