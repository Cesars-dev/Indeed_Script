"""
Indeed apply automation — attaches to AdsPower browser via debug port.
AdsPower handles fingerprint + session + proxy. nodriver handles human-like behavior.
"""
import asyncio
import os
import random
import time

import requests
import nodriver as uc
from src.nodriver_cf_verify import CFVerify

ADSPOWER_BASE = "http://localhost:50325"
ADSPOWER_API_KEY = "6690380481d7de70c40230dca72e9403005bda7f364e3e6f"


def _start_profile(user_id: str) -> dict:
    resp = requests.get(
        f"{ADSPOWER_BASE}/api/v1/browser/start",
        params={"user_id": user_id, "api_key": ADSPOWER_API_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"AdsPower start failed: {data}")
    return data["data"]


def _stop_profile(user_id: str):
    try:
        requests.get(
            f"{ADSPOWER_BASE}/api/v1/browser/stop",
            params={"user_id": user_id, "api_key": ADSPOWER_API_KEY},
            timeout=10,
        )
    except Exception:
        pass


async def _delay(min_s: float, max_s: float):
    """Random sleep with slight gaussian noise for naturalness."""
    base = random.uniform(min_s, max_s)
    noise = random.gauss(0, 0.1)
    await asyncio.sleep(max(0.05, base + noise))


async def _human_click(element):
    await element.scroll_into_view()
    await _delay(0.4, 1.0)
    await element.click()
    await _delay(0.2, 0.5)


async def _human_type(element, text: str):
    await element.click()
    await _delay(0.3, 0.7)
    for char in text:
        await element.send_keys(char)
        await asyncio.sleep(random.uniform(0.06, 0.22))


async def _human_scroll(page, steps: int = 3):
    """Scroll down in irregular chunks like a human reading."""
    for _ in range(steps):
        pixels = random.randint(180, 420)
        await page.scroll_down(pixels)
        await _delay(0.6, 1.8)


async def _screenshot(page, debug_dir: str, label: str):
    """Save a labeled screenshot to debug_dir. Silent on failure."""
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{label}.png")
    try:
        await page.save_screenshot(path)
        print(f"  📸 {path}")
    except Exception as e:
        print(f"  ⚠️  Screenshot failed ({label}): {e}")


async def _handle_cloudflare(page, timeout: int = 25) -> bool:
    """Layer 1 — Detect CF JS challenge and wait it out. Returns True when clear."""
    import time
    CF_TITLES = ["just a moment", "attention required", "checking your browser"]
    CF_CODES  = ["error code: 1020", "error code: 1015", "cf-error"]
    start = time.time()
    while time.time() - start < timeout:
        title   = (await page.evaluate("document.title")).lower()
        content = (await page.get_content()).lower()
        is_cf = (
            any(t in title for t in CF_TITLES) or
            any(c in content for c in CF_CODES) or
            "__cf_chl" in page.url
        )
        if is_cf:
            print(f"  ⚠️  Cloudflare detected ('{title}') — waiting 3s...")
            await asyncio.sleep(3)
        else:
            return True
    raise Exception(f"Cloudflare challenge did not resolve within {timeout}s")


async def _clear_cloudflare(page, timeout: int = 25) -> bool:
    """Layer 2 (Turnstile click) then Layer 1 (JS challenge wait)."""
    # Turnstile: find iframe and click it if CF challenge is present
    cf = CFVerify(_browser_tab=page, _debug=False)
    await cf.verify(_max_retries=10, _interval_between_retries=2, _reload_page_after_n_retries=3)
    # JS challenge: wait for auto-resolve
    return await _handle_cloudflare(page, timeout=timeout)


async def _detect_apply_type(page) -> str:
    """Return 'already_applied', 'external', or 'easy_apply'."""
    content = (await page.get_content()).lower()
    if "you've already applied" in content or "you already applied" in content:
        return "already_applied"
    url = page.url
    if "indeedapply" in url or "smartapply" in url:
        return "easy_apply"
    return "easy_apply"  # default — let button search confirm


async def _get_tab(browser) -> uc.Tab:
    """Leave tab[0] (AdsPower health page) untouched. Work in tab[1]."""
    tabs = browser.tabs
    # Close any excess tabs beyond index 1
    for tab in tabs[2:]:
        await tab.close()
        await asyncio.sleep(0.3)
    tabs = browser.tabs
    # Use existing tab[1] or open a fresh one
    if len(tabs) > 1:
        return tabs[1]
    return await browser.get("about:blank", new_tab=True)


async def apply_to_job(apply_url: str, docx_path, user_id: str) -> dict:
    profile_data = _start_profile(user_id)
    debug_port = int(profile_data["debug_port"])
    debug_dir = f"/tmp/apply_debug/{user_id}_{int(time.time())}"

    try:
        browser = await uc.Browser.create(host="127.0.0.1", port=debug_port)
        page = await _get_tab(browser)

        # Warmup — land on indeed.com first, idle like a human arriving at the site
        await page.get("https://www.indeed.com")
        await _clear_cloudflare(page)
        await _delay(15.0, 25.0)
        await _human_scroll(page, steps=2)
        await _delay(3.0, 6.0)

        # Navigate to job page
        await page.get(apply_url)
        await _clear_cloudflare(page)
        await _delay(3.0, 6.0)

        # Read the job page — scroll like a human reviewing it
        await _human_scroll(page, steps=random.randint(2, 4))
        await _delay(4.0, 10.0)

        # Check still logged in
        content = await page.get_content()
        if "Sign in" in content and "Sign in to Indeed" in content:
            return {"status": "failed", "reason": "Not logged in — AdsPower session expired"}

        # Detect apply type before touching anything
        apply_type = await _detect_apply_type(page)
        if apply_type == "already_applied":
            return {"status": "skipped", "reason": "Already applied to this job"}

        # Find apply button — CSS selectors first (more precise than text search)
        # Indeed's SmartApply button is a JS widget with known CSS classes/attributes
        apply_btn = None
        btn_label = None
        for selector in [
            "[data-testid='indeedApplyButton']",
            ".ia-IndeedApplyButton",
            "button[class*='IndeedApply']",
            "[data-indeed-apply]",
            "button.jobsearch-IndeedApplyButton-newDesign",
            "#indeedApplyButton",
        ]:
            apply_btn = await page.select(selector, timeout=2)
            if apply_btn:
                btn_label = f"CSS:{selector}"
                break

        # Fall back to text search if CSS selectors didn't hit
        if not apply_btn:
            for label in ["Apply with Indeed", "Apply now", "Easy Apply"]:
                apply_btn = await page.find(label, best_match=False, timeout=5)
                if apply_btn:
                    btn_label = label
                    break

        if not apply_btn:
            # Check if only external button exists
            ext_btn = await page.find("Apply on company site", best_match=True, timeout=3)
            if ext_btn:
                return {"status": "skipped", "reason": "External apply — company ATS"}
            return {"status": "failed", "reason": "No apply button found"}

        print(f"  [apply] Clicking button via: '{btn_label}'")
        await _screenshot(page, debug_dir, "pre_click_apply_btn")
        await _delay(2.0, 4.0)
        await _human_click(apply_btn)
        await _delay(2.5, 4.0)

        result = await _complete_application(page, docx_path, debug_dir=debug_dir)
        return result

    finally:
        # Return to indeed.com so AdsPower saves a warm base tab for next run
        try:
            await page.get("https://www.indeed.com")
            await asyncio.sleep(2)
        except Exception:
            pass
        _stop_profile(user_id)


async def _complete_application(page, docx_path: str, profile: dict = None, debug_dir: str = None) -> dict:
    """
    Step through the Indeed SmartApply multi-step form.

    Observed steps (order varies by job):
      1. Location  — zip/city pre-filled, street address may be empty
      2. Resume choice — "Upload a resume" vs "Build an Indeed Resume"
      3. File upload — input[type='file']
      4. Resume preview — page 1/2, just Continue
      5. Visibility — "Employers can find you" Recommended, just Continue
      6. Employer questions — Yes/No radios + numeric text inputs (years exp)
      7. Submit / Disqualification
    """
    profile = profile or {}
    years_exp = str(profile.get("years_experience", 3))
    resume_selected = False
    file_uploaded = False

    for step in range(15):
        await _delay(2.0, 3.5)
        content = await page.get_content()
        url = page.url

        # Screenshot every step — filename = step number + URL slug for easy inspection
        if debug_dir:
            slug = url.split("//")[-1].split("?")[0].replace("/", "_")[:50]
            await _screenshot(page, debug_dir, f"step_{step:02d}_{slug}")

        # === Account incomplete — Indeed redirected to settings instead of SmartApply ===
        if "indeed.com" in url and "/settings" in url:
            print(f"  [settings] Full redirect URL: {url}")
            return {"status": "failed", "reason": "Account redirected to settings — complete Indeed profile manually"}

        # === Success ===
        for success_text in ["Application submitted", "application was submitted", "You applied"]:
            if success_text in content:
                return {"status": "success", "reason": "Application submitted"}

        # === Disqualification (employer pre-screen failed) ===
        if "may not hear back from the employer" in content or "Consider additional opportunities" in content:
            return {"status": "disqualified", "reason": "Employer screening requirements not met"}

        # === Resume choice: click "Upload a resume" before continuing ===
        if not resume_selected and "Upload a resume" in content:
            upload_card = await page.find("Upload a resume", best_match=True, timeout=3)
            if upload_card:
                await _human_click(upload_card)
                resume_selected = True
                await _delay(0.8, 1.5)

        # === File upload ===
        if not file_uploaded and docx_path and os.path.exists(docx_path):
            file_input = await page.select("input[type='file']", timeout=2)
            if file_input:
                await file_input.send_file(docx_path)
                file_uploaded = True
                await _delay(3.0, 4.5)
                content = await page.get_content()

        # === Dropdowns — runs every step, no-op if all already filled ===
        await page.evaluate("""
            (() => {
                document.querySelectorAll('select').forEach(sel => {
                    if ((sel.value && sel.value !== '') || sel.offsetParent === null) return;
                    const opts = Array.from(sel.options).filter(o => o.value !== '' && !o.disabled);
                    if (!opts.length) return;
                    const lbl = document.querySelector('label[for="' + sel.id + '"]');
                    const ctx = (lbl ? lbl.textContent : (sel.closest('div,fieldset') || sel).textContent || '').toLowerCase();
                    let chosen = null;
                    if (['education', 'degree', 'diploma', 'school'].some(k => ctx.includes(k))) {
                        chosen = opts.find(o => o.text.toLowerCase().includes('high school'))
                              || opts.find(o => o.text.toLowerCase().includes('bachelor'))
                              || opts[0];
                    } else if (['employment type', 'job type', 'work type'].some(k => ctx.includes(k))) {
                        chosen = opts.find(o => o.text.toLowerCase().includes('full')) || opts[0];
                    } else {
                        chosen = opts[0];
                    }
                    if (chosen) {
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value').set;
                        setter.call(sel, chosen.value);
                        sel.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                });
            })()
        """)
        await _delay(0.3, 0.6)

        # === Employer questions: radio Yes/No + numeric text inputs ===
        if "questions" in url or "Answer these questions" in content:
            # Click "Yes" for every unanswered radio group
            await page.evaluate("""
                (() => {
                    const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                    const groups = {};
                    radios.forEach(r => { groups[r.name] = groups[r.name] || []; groups[r.name].push(r); });
                    Object.values(groups).forEach(group => {
                        if (group.some(r => r.checked)) return;
                        const yes = group.find(r => {
                            const lbl = document.querySelector('label[for="' + r.id + '"]');
                            return lbl && lbl.textContent.trim().toLowerCase() === 'yes';
                        });
                        if (yes) yes.click();
                    });
                })()
            """)
            await _delay(0.5, 1.0)
            # Fill empty experience/years inputs
            await page.evaluate(f"""
                (() => {{
                    document.querySelectorAll('input[type="text"], input[type="number"]').forEach(inp => {{
                        if (inp.value || inp.offsetParent === null) return;
                        const lbl = document.querySelector('label[for="' + inp.id + '"]');
                        const q = (lbl ? lbl.textContent : (inp.closest('div,fieldset') || document).textContent || '').toLowerCase();
                        if (!q.includes('year') && !q.includes('experience') && inp.type !== 'number') return;
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        setter.call(inp, '{years_exp}');
                        inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                        inp.dispatchEvent(new Event('change', {{bubbles: true}}));
                    }});
                }})()
            """)
            await _delay(0.5, 1.0)

        # === Submit ===
        submit = await page.find("Submit your application", best_match=True, timeout=2)
        if submit:
            await _human_click(submit)
            await _delay(3.0, 5.0)
            content = await page.get_content()
            for s in ["Application submitted", "application was submitted", "You applied"]:
                if s in content:
                    return {"status": "success", "reason": "Application submitted"}
            return {"status": "success", "reason": "Submit button clicked"}

        # === Continue / Next ===
        # Scroll down first — Continue button is often below the fold
        await _human_scroll(page, steps=1)
        advanced = False
        # CSS selector first — most reliable (avoids matching "Save and close")
        for selector in ["button[type='submit']", ".ia-continueButton", "[data-testid='continue-button']"]:
            btn = await page.select(selector, timeout=2)
            if btn:
                await _human_click(btn)
                advanced = True
                break
        # Exact text match fallback — no best_match to avoid false matches
        if not advanced:
            for label in ["Continue", "Next"]:
                btn = await page.find(label, best_match=False, timeout=2)
                if btn:
                    await _human_click(btn)
                    advanced = True
                    break
        if not advanced:
            return {"status": "failed", "reason": f"Stuck on step {step} — no action available"}

    return {"status": "failed", "reason": "Exceeded max steps without submission"}
