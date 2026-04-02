"""
SmartApply Router — 6-shot decision engine.
Replaces the monolithic _gemini_loop with:
  DOM scan → deterministic handler → Gemini Flash → Gemini Pro → fail & log

Same interface as old _gemini_loop:
  result = await apply_smartapply(page, docx_path, profile, debug_dir)
  # result = {"status": "success"|"failed"|"skipped"|"disqualified", "reason": "..."}
"""
import asyncio
import json
import os
import random
import time

from .dom_scanner import scan_dom
from .handlers import (
    handle_modal_dismiss,
    handle_file_upload,
    handle_radio_yesno,
    handle_radio_range,
    handle_text_input,
    handle_dropdown,
    handle_checkbox,
    handle_continue_button,
)
from .gemini_fallback import gemini_decide
from .logger import log


# ── Handler chain — tried in ORDER. First success wins. ──────────────────────
# Continue button is LAST so all fields get filled before we advance.
DETERMINISTIC_HANDLERS = [
    ("modal_dismiss",   handle_modal_dismiss),
    ("file_upload",     handle_file_upload),
    ("radio_yesno",     handle_radio_yesno),
    ("radio_range",     handle_radio_range),
    ("text_input",      handle_text_input),
    ("dropdown",        handle_dropdown),
    ("checkbox",        handle_checkbox),
    ("continue_button", handle_continue_button),
]


async def apply_smartapply(
    page,
    docx_path: str | None,
    profile: dict,
    debug_dir: str,
) -> dict:
    """
    6-shot router. Same return interface as _gemini_loop.
    """
    # Import screenshot/scroll from the main module (avoid circular at module level)
    from src.playwright_indeed import _screenshot, human_scroll, _execute

    prev_url = ""
    shot = 0          # reset per URL change
    filled_targets = set()  # track filled fields to detect stuck vs progress
    same_url_actions = 0  # consecutive successful actions without URL change
    file_uploaded = False  # track resume upload to avoid redundant re-uploads
    recaptcha_solved = False  # prevent re-solving on same page
    total_steps = 0
    det_steps = 0
    flash_steps = 0
    pro_steps = 0
    failed_steps = 0
    t0 = time.time()

    # Load learned Q&A patterns from Supabase (read-only, never crashes)
    from .patterns import load_dynamic_patterns
    load_dynamic_patterns()

    for step in range(25):
        total_steps = step
        url = page.url
        print(f"\n  ── step {step:02d} ── {url[:90]}")

        # ── DOM scan (<100ms) ────────────────────────────────────────────────
        try:
            dom = await scan_dom(page)
        except Exception as e:
            print(f"  ⚠️ DOM scan failed: {e}")
            await asyncio.sleep(1)
            continue

        # ── Success / disqualification signals ───────────────────────────────
        if dom["success"] or "post-apply" in url:
            log("apply_step_log", {
                "step_num": step, "url": url, "tier": "signal",
                "success": True, "action": {"action": "done"},
            })
            return {"status": "success", "reason": "Application submitted"}

        if dom["disqualified"]:
            return {"status": "disqualified", "reason": "Employer screening did not pass"}

        # ── Hard guards (same as before) ─────────────────────────────────────
        if "profile.indeed.com" in url:
            print("  ⏩ profile.indeed.com → Skip")
            try:
                skip = page.get_by_role("button", name="Skip", exact=False).first
                await skip.wait_for(state="visible", timeout=3000)
                await skip.click()
                await asyncio.sleep(1)
            except Exception:
                pass
            continue

        if "/settings" in url and "indeed.com" in url:
            return {"status": "failed", "reason": "Redirected to account settings"}

        # ── URL change → reset shot counter ──────────────────────────────────
        if url != prev_url:
            shot = 0
            same_url_actions = 0
            prev_url = url

        # ── reCAPTCHA check (before deterministic handlers) ────────────────
        if (dom.get("has_recaptcha") or "review" in url.lower()) and not recaptcha_solved:
            from src.smartapply.recaptcha import has_recaptcha, solve_recaptcha
            if await has_recaptcha(page):
                print("  🔐 reCAPTCHA detected — solving via 2Captcha...")
                if await solve_recaptcha(page):
                    recaptcha_solved = True
                    log("apply_step_log", {
                        "step_num": step, "url": url, "tier": "recaptcha",
                        "success": True,
                    })
                    await asyncio.sleep(1)
                    # Immediately try clicking Submit after solving
                    for submit_text in ["Submit your application", "Submit", "Continue"]:
                        try:
                            btn = page.get_by_role("button", name=submit_text, exact=False).first
                            if await btn.is_visible(timeout=2000) and await btn.is_enabled(timeout=1000):
                                await btn.scroll_into_view_if_needed()
                                await btn.click()
                                print(f"  ✓ Clicked '{submit_text}' after reCAPTCHA solve")
                                await asyncio.sleep(3)
                                break
                        except Exception:
                            continue
                    dom = await scan_dom(page)
                    continue
                else:
                    print("  ⚠️ reCAPTCHA not solved — escalating to Gemini")
                    log("apply_step_log", {
                        "step_num": step, "url": url, "tier": "recaptcha",
                        "success": False,
                    })
                    shot = 4  # skip deterministic, go straight to Flash

        # SHOTS 1-4: Deterministic handlers
        # ══════════════════════════════════════════════════════════════════════
        if shot < 4:
            if shot >= 1:
                # Scroll on second try to reveal hidden elements
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.3)")
                    await asyncio.sleep(random.uniform(0.8, 1.5))
                    dom = await scan_dom(page)  # re-scan after scroll
                except Exception:
                    pass

            handled = False
            handler_name = ""
            for name, handler in DETERMINISTIC_HANDLERS:
                if name == "file_upload":
                    if file_uploaded:
                        continue  # already uploaded — skip
                    ok = await handler(page, dom, profile, docx_path)
                    if ok:
                        file_uploaded = True
                else:
                    ok = await handler(page, dom, profile)
                if ok:
                    handled = True
                    handler_name = name
                    det_steps += 1
                    break

            if handled:
                same_url_actions += 1
                if same_url_actions >= 3:
                    print(f"  ⚠️ {same_url_actions} actions on same URL — escalating to Gemini")
                    shot = 4  # skip to Flash
                else:
                    shot = 0
                log("apply_step_log", {
                    "step_num": step, "url": url, "tier": "deterministic",
                    "success": True, "page_pattern": handler_name,
                })
                await asyncio.sleep(random.uniform(1.5, 3.0))  # human reads result before moving on
                continue
            else:
                shot += 1
                if shot == 4:
                    log("apply_step_log", {
                        "step_num": step, "url": url, "tier": "deterministic_miss",
                        "success": False, "dom_snapshot": dom,
                    })
                print(f"  ↓ Deterministic miss (shot {shot}/12)")
                continue

        # SHOTS 5-8: Gemini Flash with targeted prompt + screenshot
        # ══════════════════════════════════════════════════════════════════════
        if shot < 8:
            tier_label = "Flash"
            print(f"  💡 {tier_label} fallback (shot {shot + 1}/12)")
            # Escape guardrail — dismiss any open modal/overlay before screenshot
            if same_url_actions >= 2:
                try:
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)
                    dom = await scan_dom(page)  # re-scan after dismiss
                    print(f"  🔑 Pressed Escape to close any open modal")
                except Exception:
                    pass
            try:
                use_full = same_url_actions >= 2  # stuck → show full page
                screenshot = await _screenshot(page, debug_dir, f"step_{step:02d}", full_page=use_full)
            except Exception as e:
                print(f"  ⚠️ {tier_label} screenshot error: {e}")
                shot += 1
                continue

            try:
                action = await gemini_decide(screenshot, dom, profile, use_pro=False, same_url_actions=same_url_actions)
                act = action.get("action", "")
                print(f"  🤖 {tier_label} → {json.dumps(action)[:120]}")

                if act == "done":
                    return {"status": "success", "reason": action.get("reason", "Gemini confirmed submission")}
                if act == "failed":
                    return {"status": "failed", "reason": action.get("reason", "Gemini: unrecoverable")}

                ok = await _execute(page, action, docx_path)
                flash_steps += 1
                log("apply_step_log", {
                    "step_num": step, "url": url, "tier": "flash",
                    "success": ok, "action": action,
                    "dom_snapshot": dom if not ok else None,
                })
                if ok:
                    # Learn from Gemini answer on questions pages
                    if "questions" in url and action.get("target"):
                        # Extract actual question text from DOM (not Gemini's reason)
                        q_text = ""
                        a_type = "unknown"
                        target_lower = action.get("target", "").lower()
                        for rg in dom.get("radios", []):
                            opt_texts = [o["text"].lower().strip() for o in rg["options"]]
                            if any(t in target_lower for t in opt_texts if t):
                                q_text = rg["question"]
                                if len(opt_texts) == 2 and "yes" in opt_texts and "no" in opt_texts:
                                    a_type = "radio_yesno"
                                else:
                                    a_type = "radio_range"
                                break
                        if not q_text:
                            q_text = action.get("reason", "")[:500]
                            a_type = action.get("action", "unknown")
                        log("apply_patterns", {
                            "question_text": q_text[:500],
                            "answer_value": str(action.get("value") or action.get("target", ""))[:200],
                            "answer_type": a_type,
                            "source": "flash",
                        })
                    post_url = page.url
                    if post_url != url:
                        # URL changed — real progress, reset
                        shot = 0
                        same_url_actions = 0
                        filled_targets.clear()
                    else:
                        # Action succeeded but same URL — check if filling new field or stuck
                        target_key = (action.get("target", "") + "|" + str(action.get("value", ""))).lower().strip()
                        if target_key in filled_targets:
                            # Re-filling same field = stuck
                            same_url_actions += 1
                            print(f"  ⚠️ Re-filling same field (stuck #{same_url_actions})")
                        else:
                            # New field = progress
                            filled_targets.add(target_key)
                            print(f"  ✓ New field filled ({len(filled_targets)} unique on this page)")
                        if same_url_actions >= 6:
                            return {"status": "failed", "reason": f"Stuck on same page ({same_url_actions} repeated actions) — form too complex"}
                        # Scroll down to reveal Continue button or next question
                        try:
                            await page.evaluate("window.scrollBy(0, 400)")
                            await asyncio.sleep(0.8)
                        except Exception:
                            pass
                        # Re-scan DOM after scroll and try deterministic Continue
                        try:
                            dom = await scan_dom(page)
                            if await handle_continue_button(page, dom, profile):
                                print(f"  ✓ Continue clicked after scroll + {tier_label} action")
                                shot = 0  # reset — real progress
                                same_url_actions = 0
                                await asyncio.sleep(1)
                                continue
                        except Exception:
                            pass
                        # Continue not found — reset to deterministic to handle remaining fields
                        print(f"  🔄 Passing back to deterministic after {tier_label} fill (same URL #{same_url_actions})")
                        shot = 0  # reset to deterministic — let Playwright try
                    await asyncio.sleep(0.5)
                    continue
            except Exception as e:
                print(f"  ⚠️ {tier_label} error: {e}")

            shot += 1
            continue

        # SHOTS 9-12: Gemini Pro (FULL PAGE screenshot)
        # ══════════════════════════════════════════════════════════════════════
        if shot < 12:
            tier_label = "Pro"
            print(f"  🧠 {tier_label} fallback (shot {shot + 1}/12)")
            # Escape guardrail — dismiss any open modal/overlay before screenshot
            try:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                dom = await scan_dom(page)  # re-scan after dismiss
                print(f"  🔑 Pro: pressed Escape to close any open modal")
            except Exception:
                pass
            try:
                screenshot = await _screenshot(page, debug_dir, f"step_{step:02d}_full", full_page=True)
            except Exception as e:
                print(f"  ⚠️ {tier_label} screenshot error: {e}")
                shot += 1
                continue

            try:
                action = await gemini_decide(screenshot, dom, profile, use_pro=True, same_url_actions=same_url_actions)
                act = action.get("action", "")
                print(f"  🤖 {tier_label} → {json.dumps(action)[:120]}")

                if act == "done":
                    return {"status": "success", "reason": action.get("reason", "Gemini Pro confirmed submission")}
                if act == "failed":
                    return {"status": "failed", "reason": action.get("reason", "Gemini Pro: unrecoverable")}

                ok = await _execute(page, action, docx_path)
                pro_steps += 1
                log("apply_step_log", {
                    "step_num": step, "url": url, "tier": "pro",
                    "success": ok, "action": action,
                    "dom_snapshot": dom if not ok else None,
                    "screenshot_path": f"{debug_dir}/step_{step:02d}.jpg",
                })
                if ok:
                    # Learn from Gemini answer on questions pages
                    if "questions" in url and action.get("target"):
                        # Extract actual question text from DOM (not Gemini's reason)
                        q_text = ""
                        a_type = "unknown"
                        target_lower = action.get("target", "").lower()
                        for rg in dom.get("radios", []):
                            opt_texts = [o["text"].lower().strip() for o in rg["options"]]
                            if any(t in target_lower for t in opt_texts if t):
                                q_text = rg["question"]
                                if len(opt_texts) == 2 and "yes" in opt_texts and "no" in opt_texts:
                                    a_type = "radio_yesno"
                                else:
                                    a_type = "radio_range"
                                break
                        if not q_text:
                            q_text = action.get("reason", "")[:500]
                            a_type = action.get("action", "unknown")
                        log("apply_patterns", {
                            "question_text": q_text[:500],
                            "answer_value": str(action.get("value") or action.get("target", ""))[:200],
                            "answer_type": a_type,
                            "source": "pro",
                        })
                    post_url = page.url
                    if post_url != url:
                        shot = 0
                        same_url_actions = 0
                        filled_targets.clear()
                    else:
                        target_key = (action.get("target", "") + "|" + str(action.get("value", ""))).lower().strip()
                        if target_key in filled_targets:
                            same_url_actions += 1
                            print(f"  ⚠️ Re-filling same field (stuck #{same_url_actions})")
                        else:
                            filled_targets.add(target_key)
                            print(f"  ✓ New field filled ({len(filled_targets)} unique on this page)")
                        if same_url_actions >= 6:
                            return {"status": "failed", "reason": f"Stuck on same page ({same_url_actions} repeated actions) — form too complex"}
                        # Scroll + pass back to deterministic
                        try:
                            await page.evaluate("window.scrollBy(0, 400)")
                            await asyncio.sleep(0.8)
                        except Exception:
                            pass
                        try:
                            dom = await scan_dom(page)
                            if await handle_continue_button(page, dom, profile):
                                print(f"  ✓ Continue clicked after scroll + {tier_label} action")
                                shot = 0
                                same_url_actions = 0
                                await asyncio.sleep(1)
                                continue
                        except Exception:
                            pass
                        print(f"  🔄 Passing back to deterministic after {tier_label} fill (same URL #{same_url_actions})")
                        shot = 0  # reset to deterministic
                    await asyncio.sleep(0.5)
                    continue
            except Exception as e:
                print(f"  ⚠️ {tier_label} error: {e}")

            shot += 1
            continue

        # ALL 12 SHOTS EXHAUSTED — log failure, move on
        # ══════════════════════════════════════════════════════════════════════
        failed_steps += 1
        log("apply_step_log", {
            "step_num": step, "url": url, "tier": "exhausted",
            "success": False, "dom_snapshot": dom,
            "screenshot_path": f"{debug_dir}/step_{step:02d}.jpg",
            "error_msg": "12 shots exhausted — likely new pattern",
        })
        elapsed = round(time.time() - t0, 1)
        log("apply_runs", {
            "status": "failed",
            "reason": f"12 shots exhausted at step {step}",
            "total_steps": step,
            "deterministic_steps": det_steps,
            "flash_steps": flash_steps,
            "pro_steps": pro_steps,
            "failed_steps": failed_steps,
            "elapsed_s": elapsed,
            "last_url": url,
            "debug_dir": debug_dir,
        })
        return {
            "status": "failed",
            "reason": f"12 shots exhausted at step {step} — likely new pattern",
        }

    elapsed = round(time.time() - t0, 1)
    log("apply_step_log", {
        "step_num": total_steps, "url": prev_url, "tier": "exhausted",
        "success": False, "error_msg": f"Exceeded 25 steps ({elapsed}s)",
    })
    log("apply_runs", {
        "status": "failed", "reason": f"Exceeded 25 steps ({elapsed}s)",
        "total_steps": total_steps, "deterministic_steps": det_steps,
        "flash_steps": flash_steps, "pro_steps": pro_steps,
        "elapsed_s": elapsed, "debug_dir": debug_dir,
    })
    return {"status": "failed", "reason": f"Exceeded 25 steps ({elapsed}s)"}
