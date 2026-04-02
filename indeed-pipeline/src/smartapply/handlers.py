"""
Deterministic form handlers — no Gemini needed.
Each handler: find unanswered element → 3-5s human delay → act → return bool.
"""
import asyncio
import os
import random

from .patterns import match_yesno, match_range, match_text_input, get_dynamic_answer


async def _human_delay():
    """3-5s random delay to simulate human reading + thinking + acting."""
    await asyncio.sleep(random.uniform(3.0, 5.0))


# ── Handler 0: Modal dismissal ────────────────────────────────────────────────

async def handle_modal_dismiss(page, dom: dict, profile: dict) -> bool:
    """Dismiss Indeed modals that block form interaction.
    
    Handles: 'Save application progress', 'What the employer sees',
    and any other modal overlay that appears during the flow.
    Early-exit: skips entirely if no dialog is visible.
    """
    # Quick check — skip if no dialog/modal is visible
    try:
        has_dialog = await page.evaluate("""() => {
            const d = document.querySelector('[role="dialog"], [aria-modal="true"]');
            return d !== null && d.offsetParent !== null;
        }""")
        if not has_dialog:
            return False
    except Exception:
        return False

    print("  🔲 Modal detected — attempting dismiss")

    # Try known dismiss button texts
    for text in ["Don't save", "Close", "Got it", "Dismiss", "No thanks"]:
        try:
            btn = page.get_by_role("button", name=text, exact=False).first
            if await btn.is_visible(timeout=300):
                await btn.click()
                print(f"  ✓ dismissed modal: '{text}'")
                await asyncio.sleep(0.5)
                return True
        except Exception:
            continue

    # Fallback: close via X/close button selectors
    for sel in [
        "[aria-label='Close']",
        "[aria-label='close']",
        "button[class*='CloseButton']",
        "[data-testid*='close']",
        "button.ia-CloseButton",
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=300):
                await btn.click()
                print(f"  ✓ closed modal via {sel}")
                await asyncio.sleep(0.5)
                return True
        except Exception:
            continue

    # Last resort: press Escape
    try:
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.5)
        print("  ✓ pressed Escape to dismiss modal")
        return True
    except Exception:
        pass

    return False


# ── Handler 1: File upload ────────────────────────────────────────────────────

async def handle_file_upload(page, dom: dict, profile: dict, docx_path: str | None = None) -> bool:
    """Upload resume/CV if a visible file input exists."""
    if dom["file_inputs"] == 0 or not docx_path:
        return False
    if not os.path.exists(docx_path):
        return False
    try:
        fi = page.locator("input[type='file']").first
        await fi.wait_for(state="attached", timeout=1500)
        await fi.set_input_files(docx_path)
        print(f"  📎 Uploaded: {os.path.basename(docx_path)}")
        await asyncio.sleep(random.uniform(2.0, 4.0))
        return True
    except Exception:
        return False


# ── Handler 2: Yes/No radios ─────────────────────────────────────────────────

async def handle_radio_yesno(page, dom: dict, profile: dict) -> bool:
    """Answer Yes/No radio questions from known keyword patterns."""
    for rg in dom["radios"]:
        if any(o["selected"] for o in rg["options"]):
            continue  # already answered

        # Only handle 2-option groups (Yes/No)
        opt_texts = [o["text"].strip().lower() for o in rg["options"]]
        if not (len(opt_texts) == 2 and "yes" in opt_texts and "no" in opt_texts):
            continue

        answer = match_yesno(rg["question"])
        if not answer:
            # Try dynamic patterns
            dyn = get_dynamic_answer(rg["question"])
            if dyn and dyn[0] == "radio_yesno":
                answer = dyn[1]
        if not answer:
            continue

        for opt in rg["options"]:
            if opt["text"].strip().lower() == answer.lower():
                await _human_delay()
                # Try input[name][value] first (most reliable)
                try:
                    radio = page.locator(f"input[name='{rg['name']}'][value='{opt['value']}']")
                    el = radio.first
                    await el.wait_for(state="attached", timeout=2000)
                    await el.check(force=True)
                    print(f"  ✓ radio: '{rg['question'][:50]}' → {answer}")
                    return True
                except Exception:
                    pass
                # Fallback: click label
                try:
                    label = page.get_by_label(opt["text"], exact=True)
                    await label.first.click()
                    print(f"  ✓ radio (label): '{rg['question'][:50]}' → {answer}")
                    return True
                except Exception:
                    pass
    return False


# ── Handler 3: Range/enum radios ──────────────────────────────────────────────

async def handle_radio_range(page, dom: dict, profile: dict) -> bool:
    """Answer range/enum radios (experience years, travel %, shift, etc.)."""
    for rg in dom["radios"]:
        if any(o["selected"] for o in rg["options"]):
            continue

        opt_texts = [o["text"].strip() for o in rg["options"] if o["text"].strip()]
        if len(opt_texts) < 2:
            continue
        # Skip pure Yes/No groups (handled by yesno handler)
        if set(t.lower() for t in opt_texts) == {"yes", "no"}:
            continue

        answer = match_range(rg["question"], opt_texts)
        if not answer:
            # Try dynamic patterns
            dyn = get_dynamic_answer(rg["question"])
            if dyn and dyn[0] == "radio_range":
                answer = dyn[1]
        if not answer:
            continue

        for opt in rg["options"]:
            if opt["text"].strip() == answer:
                await _human_delay()
                try:
                    radio = page.locator(f"input[name='{rg['name']}'][value='{opt['value']}']")
                    el = radio.first
                    await el.wait_for(state="attached", timeout=2000)
                    await el.check(force=True)
                    print(f"  ✓ range: '{rg['question'][:50]}' → {answer}")
                    return True
                except Exception:
                    pass
                try:
                    label = page.get_by_label(opt["text"], exact=True)
                    await label.first.click()
                    print(f"  ✓ range (label): '{rg['question'][:50]}' → {answer}")
                    return True
                except Exception:
                    pass
    return False


# ── Handler 4: Text inputs ───────────────────────────────────────────────────

async def handle_text_input(page, dom: dict, profile: dict) -> bool:
    """Fill text/number/phone inputs from profile data or defaults."""
    for inp in dom["inputs"]:
        if inp["value"]:  # already filled
            continue

        value = match_text_input(inp["label"], profile)
        if not value:
            continue

        await _human_delay()
        try:
            if inp["id"]:
                field = page.locator(f"#{inp['id']}")
            else:
                field = page.get_by_label(inp["label"], exact=False)
            el = field.first
            await el.wait_for(state="visible", timeout=2000)
            await el.fill(value)
            await asyncio.sleep(random.uniform(0.8, 1.5))
            print(f"  ✓ text: '{inp['label'][:40]}' → '{value}'")
            return True
        except Exception:
            continue
    return False


# ── Handler 5: Dropdown selects ───────────────────────────────────────────────

async def handle_dropdown(page, dom: dict, profile: dict) -> bool:
    """Select dropdown values using label matching."""
    for sel in dom["selects"]:
        # Skip if already has a meaningful selection (not the placeholder)
        if sel["value"] and sel["value"] != "":
            # Check if current value is a placeholder like "" or "Select..."
            current_opt = next((o for o in sel["options"] if o["selected"]), None)
            if current_opt and current_opt["text"] and not current_opt["text"].startswith("Select"):
                continue

        # Get non-placeholder options
        real_options = [o for o in sel["options"] if o["value"] and o["value"] != ""]
        if not real_options:
            continue

        # Try to match from profile
        value = match_text_input(sel["label"], profile) if sel["label"] else None

        if value:
            # Fuzzy match value against available options
            best_opt = None
            for opt in real_options:
                if value.lower() in opt["text"].lower() or opt["text"].lower() in value.lower():
                    best_opt = opt["value"]
                    break
            if not best_opt:
                best_opt = real_options[0]["value"]
        else:
            # Default: pick first real option
            best_opt = real_options[0]["value"]

        await _human_delay()
        try:
            if sel.get("id"):
                select_el = page.locator(f"select#{sel['id']}")
            else:
                select_el = page.get_by_label(sel["label"], exact=False)
            await select_el.first.select_option(value=best_opt)
            opt_text = next((o["text"] for o in real_options if o["value"] == best_opt), best_opt)
            print(f"  ✓ select: '{sel['label'][:40]}' → '{opt_text}'")
            return True
        except Exception:
            continue
    return False


# ── Handler 6: Checkboxes ────────────────────────────────────────────────────

async def handle_checkbox(page, dom: dict, profile: dict) -> bool:
    """Check any unchecked visible checkboxes."""
    for cb in dom["checkboxes"]:
        if cb["checked"]:
            continue

        await _human_delay()
        try:
            if cb["id"]:
                el = page.locator(f"#{cb['id']}")
            else:
                el = page.get_by_label(cb["label"], exact=False)
            await el.first.check()
            print(f"  ✓ checkbox: '{cb['label'][:40]}'")
            return True
        except Exception:
            continue
    return False


# ── Handler 7: Continue / Submit button ───────────────────────────────────────

async def handle_continue_button(page, dom: dict, profile: dict) -> bool:
    """Click Continue/Next/Submit/Review when all fields look answered."""
    # Check for unanswered required elements first
    has_unanswered_radio = any(
        not any(o["selected"] for o in rg["options"])
        for rg in dom["radios"]
    )
    has_empty_required_input = any(
        not inp["value"] and inp["required"]
        for inp in dom["inputs"]
    )
    # Filter out false-positive "errors" (reCAPTCHA text, privacy banners, etc.)
    real_errors = [
        e for e in dom["errors"]
        if not any(fp in e.lower() for fp in [
            "recaptcha", "cookie", "privacy", "protected by",
            "what the employer sees", "save application",
            "get email updates", "i'm not a robot", "terms of service",
        ])
    ]
    has_errors = len(real_errors) > 0

    is_review_page = "review" in page.url.lower()

    # If there are unanswered questions or errors, don't click Continue (unless we are on the review page)
    if not is_review_page and (has_unanswered_radio or has_empty_required_input or has_errors):
        return False

    # Find and click the Continue/Submit button
    for btn in dom["buttons"]:
        if btn["disabled"]:
            continue
        text_lower = btn["text"].lower().strip()
        # "review" must be whole-word match — avoid "preview what employers see"
        is_review = text_lower == "review" or text_lower.startswith("review ")
        if any(w in text_lower for w in ["continue", "next", "submit"]) or is_review:
            # Skip "Save and close" / "Sign in" / "Preview..." etc
            if any(skip in text_lower for skip in ["save", "close", "sign in", "log in", "preview"]):
                continue
            await _human_delay()
            pre_click_url = page.url
            for sel in [
                page.get_by_role("button", name=btn["text"], exact=False),
                page.get_by_text(btn["text"], exact=True),
            ]:
                try:
                    el = sel.first
                    await el.wait_for(state="visible", timeout=2000)
                    await el.scroll_into_view_if_needed()
                    await el.click()
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    if page.url == pre_click_url:
                        print(f"  ⚠️ button: '{btn['text'][:40]}' clicked but page didn't advance")
                        return False  # URL didn't change → likely validation error; let router escalate
                    else:
                        print(f"  ✓ button: '{btn['text'][:40]}' → page advanced")
                        return True
                except Exception:
                    continue
    print(f"  [DEBUG] Buttons found: {[b['text'] for b in dom['buttons']]}")
    return False
