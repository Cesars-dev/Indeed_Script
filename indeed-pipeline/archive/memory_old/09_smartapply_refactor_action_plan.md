# SmartApply v2 — Surgeon Framework Step 2: ACTION PLAN

> Step-by-step implementation based on the audit.
> Every file change, function signature, and code pattern specified.

---

## Overview

**What changes:** Replace `_gemini_loop_inner()` with a router + handlers architecture.
**What stays:** `apply_to_job()`, stealth injection, CF bypass, `_execute()`, warmup.
**Interface:** `apply_to_job()` still returns `{"status": "...", "reason": "..."}` — no external API change.

---

## File Structure (after refactor)

```
src/
  playwright_indeed.py          ← TRIMMED: entry point, stealth, warmup, CF
  smartapply/
    __init__.py                 ← exports apply_smartapply()
    router.py                  ← 6-shot loop + scenario detection
    dom_scanner.py              ← _scan_dom() JS extraction
    handlers.py                 ← all 10 deterministic handlers
    gemini_fallback.py          ← targeted prompt builder + _gemini_decide()
    execute.py                  ← moved from playwright_indeed.py (unchanged)
    logger.py                   ← fire-and-forget Supabase logging
    patterns.py                 ← answer mappings + pattern registry loader
```

---

## Step 1: Create `src/smartapply/` Package

### `src/smartapply/__init__.py`
```python
from .router import apply_smartapply
```

---

## Step 2: Create `src/smartapply/dom_scanner.py`

Single function — runs JS in browser, returns structured form data.

```python
async def scan_dom(page) -> dict:
    """Extract all form elements from current page. <100ms, no API call."""
    return await page.evaluate("""() => {
        const result = {
            url: window.location.href,
            buttons: [],
            radios: [],
            inputs: [],
            selects: [],
            checkboxes: [],
            file_inputs: 0,
            success: false,
            disqualified: false,
            errors: []
        };

        // Buttons
        result.buttons = [...document.querySelectorAll('button, [role="button"], a[class*="btn"]')]
            .filter(b => b.offsetParent !== null)
            .map(b => ({
                text: b.textContent.trim().substring(0, 60),
                type: b.type || '',
                disabled: b.disabled
            }));

        // Radio groups — find by fieldset or nearby question text
        const radioInputs = document.querySelectorAll('input[type="radio"]');
        const processedNames = new Set();
        radioInputs.forEach(r => {
            if (processedNames.has(r.name)) return;
            processedNames.add(r.name);
            
            const container = r.closest('fieldset') || r.closest('[role="radiogroup"]')
                || r.closest('[data-testid]') || r.parentElement?.parentElement?.parentElement;
            
            let question = '';
            if (container) {
                const legend = container.querySelector('legend, label:first-of-type, span[id*="label"]');
                question = legend?.textContent?.trim() || '';
                // If no legend, get first text block in container
                if (!question) {
                    for (const el of container.querySelectorAll('span, p, div, label')) {
                        const t = el.textContent?.trim();
                        if (t && t.length > 5 && !['Yes','No'].includes(t)) {
                            question = t.substring(0, 120);
                            break;
                        }
                    }
                }
            }
            
            const siblings = document.querySelectorAll(`input[name="${r.name}"]`);
            const options = [...siblings].map(s => ({
                text: (s.labels?.[0] || s.nextElementSibling)?.textContent?.trim() || '',
                value: s.value,
                selected: s.checked
            }));
            
            result.radios.push({ question, options, name: r.name });
        });

        // Text inputs
        result.inputs = [...document.querySelectorAll(
            'input[type="text"], input[type="number"], input[type="tel"], input[type="email"], textarea'
        )]
            .filter(i => i.offsetParent !== null && !i.readOnly)
            .map(i => ({
                label: (document.querySelector(`label[for="${i.id}"]`)?.textContent?.trim()
                    || i.getAttribute('aria-label')
                    || i.placeholder || '').substring(0, 100),
                value: i.value,
                required: i.required || i.getAttribute('aria-required') === 'true',
                type: i.type,
                id: i.id || ''
            }));

        // Selects
        result.selects = [...document.querySelectorAll('select')]
            .filter(s => s.offsetParent !== null)
            .map(s => ({
                label: (document.querySelector(`label[for="${s.id}"]`)?.textContent?.trim() || '').substring(0, 100),
                value: s.value,
                options: [...s.options].map(o => ({ text: o.text, value: o.value, selected: o.selected }))
            }));

        // Checkboxes
        result.checkboxes = [...document.querySelectorAll('input[type="checkbox"]')]
            .filter(c => c.offsetParent !== null)
            .map(c => ({
                label: (c.labels?.[0])?.textContent?.trim()?.substring(0, 100) || '',
                checked: c.checked,
                id: c.id || ''
            }));

        // File inputs
        result.file_inputs = [...document.querySelectorAll('input[type="file"]')]
            .filter(f => f.offsetParent !== null).length;

        // Success signals
        const bodyText = document.body.textContent;
        result.success = bodyText.includes('Application submitted')
            || bodyText.includes('application was submitted')
            || bodyText.includes('You applied');
        
        result.disqualified = bodyText.includes('may not hear back')
            || bodyText.includes('Consider additional opportunities');

        // Error messages
        result.errors = [...document.querySelectorAll('[class*="error"], [role="alert"], [class*="Error"]')]
            .filter(e => e.offsetParent !== null)
            .map(e => e.textContent.trim().substring(0, 100))
            .filter(t => t.length > 0);

        return result;
    }""")
```

**~100 lines.** Returns everything the router needs to decide.

---

## Step 3: Create `src/smartapply/patterns.py`

Answer mappings + pattern registry.

```python
"""Known answer patterns for SmartApply form questions."""

# Keyword → answer mapping for Yes/No radios
# Key = lowercase substring found in question text
# Value = answer to select
YESNO_ANSWERS = {
    "authorized to work": "Yes",
    "legally authorized": "Yes",
    "speak spanish": "Yes",
    "habla español": "Yes",
    "high school diploma": "Yes",
    "reliable transportation": "Yes",
    "reliably commute": "Yes",
    "willing to relocate": "Yes",
    "background check": "Yes",
    "drug test": "Yes",
    "drug screen": "Yes",
    "18 years": "Yes",
    "at least 18": "Yes",
    "work in the united states": "Yes",
    "currently employed": "No",
    "non-compete": "No",
    "cdl": "No",
    "commercial driver": "No",
}

# Keyword → answer for range/enum radios
RANGE_ANSWERS = {
    "years of experience": "2 - 5 years",
    "microsoft office": "2 - 5 years",
    "customer service": "2 - 5 years",
    "travel": "Less than 20%",
    "willing to travel": "Less than 20%",
    "overtime": "Yes",
    "shift": "Day shift",
    "schedule": "Full-time",
    "employment type": "Full-time",
    "start date": "Immediately",
    "availability": "Immediately",
}

# Keyword → profile field for text inputs
TEXT_MAPPINGS = {
    "phone": "phone",
    "mobile": "phone",
    "hourly": "salary_hr",
    "wage": "salary_hr",
    "annual salary": "salary_yr",
    "salary expectation": "salary_yr",
    "years of experience": "years_exp",
    "years experience": "years_exp",
}

# Default values when no profile field matches
TEXT_DEFAULTS = {
    "years": "3",
    "experience": "3",
    "gpa": "3.5",
}


def match_yesno(question: str) -> str | None:
    """Return 'Yes' or 'No' if question matches a known pattern."""
    q = question.lower()
    for keyword, answer in YESNO_ANSWERS.items():
        if keyword in q:
            return answer
    return None


def match_range(question: str, options: list[str]) -> str | None:
    """Return best option text if question matches a range pattern."""
    q = question.lower()
    for keyword, answer in RANGE_ANSWERS.items():
        if keyword in q:
            # Fuzzy match against actual options
            answer_lower = answer.lower()
            for opt in options:
                if answer_lower in opt.lower() or opt.lower() in answer_lower:
                    return opt
            # Exact not found — return first option as fallback
            return options[0] if options else None
    return None


def match_text_input(label: str, profile: dict) -> str | None:
    """Return value to fill if label matches a known pattern."""
    l = label.lower()
    for keyword, field in TEXT_MAPPINGS.items():
        if keyword in l:
            return profile.get(field, "")
    for keyword, default in TEXT_DEFAULTS.items():
        if keyword in l:
            return default
    return None


# Dynamic patterns loaded from Supabase at startup
_dynamic_patterns: list[dict] = []

def load_dynamic_patterns():
    """Load patterns from Supabase apply_patterns table."""
    global _dynamic_patterns
    try:
        import requests, os
        r = requests.get(
            f"{os.getenv('SUPABASE_URL')}/rest/v1/apply_patterns",
            params={"select": "*", "order": "created_at.desc"},
            headers={
                "apikey": os.getenv("SUPABASE_KEY"),
                "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}",
            },
            timeout=10,
        )
        _dynamic_patterns = r.json() if r.ok else []
        print(f"[patterns] Loaded {len(_dynamic_patterns)} dynamic patterns")
    except Exception as e:
        print(f"[patterns] WARNING: {e}")
        _dynamic_patterns = []
```

**~120 lines.** Pure data + simple matchers.

---

## Step 4: Create `src/smartapply/handlers.py`

10 deterministic handlers. Each is 10-20 lines.

```python
"""Deterministic form handlers — no Gemini needed."""
import asyncio
import random

from .patterns import match_yesno, match_range, match_text_input


async def _human_delay():
    """3-5s random delay to mimic human reading + thinking."""
    await asyncio.sleep(random.uniform(3.0, 5.0))


async def handle_continue_button(page, dom, profile) -> bool:
    """Click Continue/Next/Submit when all visible fields are answered."""
    for btn in dom["buttons"]:
        if btn["disabled"]:
            continue
        text = btn["text"].lower()
        if any(w in text for w in ["continue", "next", "submit", "review"]):
            await _human_delay()
            for selector in [
                page.get_by_role("button", name=btn["text"], exact=False),
                page.get_by_text(btn["text"], exact=False),
            ]:
                try:
                    el = selector.first
                    await el.wait_for(state="visible", timeout=2000)
                    await el.click()
                    await asyncio.sleep(0.5)
                    return True
                except Exception:
                    continue
    return False


async def handle_radio_yesno(page, dom, profile) -> bool:
    """Answer Yes/No radio questions from known patterns."""
    for radio_group in dom["radios"]:
        # Skip already answered
        if any(opt["selected"] for opt in radio_group["options"]):
            continue
        
        answer = match_yesno(radio_group["question"])
        if not answer:
            continue
        
        # Find the right option to click
        for opt in radio_group["options"]:
            if opt["text"].lower().strip() == answer.lower():
                await _human_delay()
                # Click by name within radio group
                try:
                    radio = page.locator(f"input[name='{radio_group['name']}'][value='{opt['value']}']")
                    await radio.first.check()
                    return True
                except Exception:
                    # Fallback: click label text
                    try:
                        label = page.get_by_label(opt["text"], exact=True)
                        await label.first.click()
                        return True
                    except Exception:
                        continue
    return False


async def handle_radio_range(page, dom, profile) -> bool:
    """Answer range/enum radios (experience, travel %, etc.)."""
    for radio_group in dom["radios"]:
        if any(opt["selected"] for opt in radio_group["options"]):
            continue
        
        option_texts = [o["text"] for o in radio_group["options"]]
        answer = match_range(radio_group["question"], option_texts)
        if not answer:
            continue
        
        for opt in radio_group["options"]:
            if opt["text"] == answer:
                await _human_delay()
                try:
                    radio = page.locator(f"input[name='{radio_group['name']}'][value='{opt['value']}']")
                    await radio.first.check()
                    return True
                except Exception:
                    try:
                        label = page.get_by_label(opt["text"], exact=True)
                        await label.first.click()
                        return True
                    except Exception:
                        continue
    return False


async def handle_text_input(page, dom, profile) -> bool:
    """Fill text/number inputs from profile data."""
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
            await field.first.fill(value)
            await asyncio.sleep(0.3)
            return True
        except Exception:
            continue
    return False


async def handle_dropdown(page, dom, profile) -> bool:
    """Select dropdown values using fuzzy matching."""
    for sel in dom["selects"]:
        if sel["value"]:  # already has a selection
            continue
        
        # Try to match label to known patterns
        value = match_text_input(sel["label"], profile)
        if not value:
            # Default: pick first non-empty option
            non_empty = [o for o in sel["options"] if o["value"]]
            if non_empty:
                value = non_empty[0]["value"]
            else:
                continue
        
        await _human_delay()
        try:
            if sel.get("id"):
                select_el = page.locator(f"select#{sel['id']}")
            else:
                select_el = page.get_by_label(sel["label"], exact=False)
            await select_el.first.select_option(value=value)
            return True
        except Exception:
            continue
    return False


async def handle_checkbox(page, dom, profile) -> bool:
    """Check any unchecked checkboxes."""
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
            return True
        except Exception:
            continue
    return False


async def handle_file_upload(page, dom, profile, docx_path) -> bool:
    """Upload resume if file input is visible."""
    if dom["file_inputs"] == 0:
        return False
    if not docx_path:
        return False
    
    import os
    if not os.path.exists(docx_path):
        return False
    
    try:
        fi = page.locator("input[type='file']").first
        await fi.wait_for(state="attached", timeout=1000)
        await fi.set_input_files(docx_path)
        print(f"  📎 Uploaded: {os.path.basename(docx_path)}")
        await asyncio.sleep(1)
        return True
    except Exception:
        return False
```

**~180 lines.** Each handler: find unanswered element → delay → act → return bool.

---

## Step 5: Create `src/smartapply/gemini_fallback.py`

Targeted prompts only for unknowns.

```python
"""Gemini fallback — only called when deterministic handlers fail."""
import json
import os
from google import genai
from google.genai import types

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
FLASH_MODEL = "gemini-2.5-flash"
PRO_MODEL = "gemini-3.1-pro-preview"


def build_targeted_prompt(dom: dict, profile: dict) -> str:
    """Build a short, targeted prompt from DOM data — not a generic page description."""
    parts = ["You are filling a job application form. Given the DOM state below, pick the SINGLE NEXT ACTION.\n"]
    
    # Unanswered radios
    for rg in dom["radios"]:
        if not any(o["selected"] for o in rg["options"]):
            opts = ", ".join(o["text"] for o in rg["options"])
            parts.append(f"UNANSWERED RADIO: \"{rg['question']}\" → Options: [{opts}]")
    
    # Empty inputs
    for inp in dom["inputs"]:
        if not inp["value"] and inp["required"]:
            parts.append(f"EMPTY REQUIRED INPUT: \"{inp['label']}\" (type: {inp['type']})")
    
    # Empty selects
    for sel in dom["selects"]:
        if not sel["value"]:
            opts = ", ".join(o["text"] for o in sel["options"][:5])
            parts.append(f"EMPTY DROPDOWN: \"{sel['label']}\" → Options: [{opts}]")
    
    # Errors on page
    for err in dom["errors"]:
        parts.append(f"ERROR: {err}")
    
    # Available buttons
    btns = [b["text"] for b in dom["buttons"] if not b["disabled"]]
    parts.append(f"BUTTONS: {btns}")
    
    # Profile context
    parts.append(f"\nAPPLICANT: {profile.get('name', '')}, {profile.get('years_exp', '3')} yrs exp, ${profile.get('salary_hr', '25')}/hr")
    
    parts.append("""
Reply with ONLY valid JSON:
{"action": "click|fill|select_option|check|scroll", "target": "exact element text", "value": "text to type (fill/select only)", "reason": "one line"}""")
    
    return "\n".join(parts)


async def gemini_decide(screenshot: bytes, dom: dict, profile: dict, use_pro: bool = False) -> dict:
    """Send targeted prompt + screenshot to Gemini. Returns action dict."""
    prompt = build_targeted_prompt(dom, profile)
    model = PRO_MODEL if use_pro else FLASH_MODEL
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=screenshot, mime_type="image/jpeg"),
            prompt,
        ],
    )
    raw = resp.text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return json.loads(raw)
```

**~70 lines.** Targeted prompt is 10-15 lines, not 100.

---

## Step 6: Create `src/smartapply/logger.py`

Fire-and-forget Supabase logging.

```python
"""Non-blocking Supabase logger. Never blocks the pipeline."""
import asyncio
import os
import json
import aiohttp

_SB_URL = os.getenv("SUPABASE_URL", "")
_SB_KEY = os.getenv("SUPABASE_KEY", "")


async def _post(table: str, data: dict):
    """POST to Supabase REST API. Runs in background, never blocks."""
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{_SB_URL}/rest/v1/{table}",
                json=data,
                headers={
                    "apikey": _SB_KEY,
                    "Authorization": f"Bearer {_SB_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=5),
            )
    except Exception:
        pass  # fire and forget — never crash the pipeline


def log(table: str, data: dict):
    """Fire-and-forget log. Returns immediately."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_post(table, data))
    except RuntimeError:
        pass  # no event loop — skip
```

**~30 lines.**

---

## Step 7: Create `src/smartapply/execute.py`

Move `_execute()` from `playwright_indeed.py` — **unchanged**. 
Just move L344-635 into this file as a standalone function.

**~290 lines, no changes to logic.**

---

## Step 8: Create `src/smartapply/router.py` — THE CORE

```python
"""SmartApply Router — 6-shot decision engine."""
import asyncio
import os
import random
import time

from .dom_scanner import scan_dom
from .handlers import (
    handle_continue_button,
    handle_radio_yesno,
    handle_radio_range,
    handle_text_input,
    handle_dropdown,
    handle_checkbox,
    handle_file_upload,
)
from .gemini_fallback import gemini_decide
from .execute import execute_action
from .logger import log


# Handler chain — tried in order. First success wins.
DETERMINISTIC_HANDLERS = [
    handle_file_upload,     # upload if file input visible
    handle_radio_yesno,     # Yes/No questions
    handle_radio_range,     # experience/travel/shift ranges
    handle_text_input,      # phone/wage/years
    handle_dropdown,        # select dropdowns
    handle_checkbox,        # check checkboxes
    handle_continue_button, # Continue/Submit (LAST — only after all filled)
]


async def apply_smartapply(page, docx_path, profile, debug_dir) -> dict:
    """
    6-shot router replacing _gemini_loop.
    Same interface: returns {"status": ..., "reason": ...}
    """
    from ..playwright_indeed import _screenshot, human_scroll
    
    run_id = None  # set after first log
    prev_url = ""
    file_uploaded = False
    step = 0
    
    for step in range(50):
        url = page.url
        print(f"\n  ── step {step:02d} ── {url[:90]}")
        
        # ── DOM scan (free, <100ms) ──
        try:
            dom = await scan_dom(page)
        except Exception as e:
            print(f"  ⚠️ DOM scan error: {e}")
            await asyncio.sleep(1)
            continue
        
        # ── Success / failure signals ──
        if dom["success"]:
            log("apply_runs", {"status": "success", "total_steps": step})
            return {"status": "success", "reason": "Application submitted"}
        
        if dom["disqualified"]:
            log("apply_runs", {"status": "disqualified", "total_steps": step})
            return {"status": "disqualified", "reason": "Employer screening did not pass"}
        
        # ── Hard guards ──
        if "profile.indeed.com" in url:
            print(f"  ⏩ profile.indeed.com → Skip")
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
        
        # ── URL change resets shot counter ──
        if url != prev_url:
            shot = 0
            prev_url = url
        
        # ── 6-SHOT BUDGET ──
        shot = getattr(apply_smartapply, '_shot', 0)
        
        # Shots 1-2: Deterministic handlers
        if shot < 2:
            if shot == 1:
                # Scroll on second try to reveal hidden elements
                try:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.3)")
                    await asyncio.sleep(0.3)
                    dom = await scan_dom(page)  # re-scan after scroll
                except Exception:
                    pass
            
            handled = False
            for handler in DETERMINISTIC_HANDLERS:
                if handler == handle_file_upload:
                    ok = await handler(page, dom, profile, docx_path)
                else:
                    ok = await handler(page, dom, profile)
                if ok:
                    handled = True
                    log("apply_step_log", {
                        "step_num": step, "url": url,
                        "tier": "deterministic", "success": True,
                        "page_pattern": handler.__name__
                    })
                    break
            
            if handled:
                shot = 0  # reset on success
                apply_smartapply._shot = 0
                await asyncio.sleep(0.5)
                continue
            else:
                shot += 1
                apply_smartapply._shot = shot
                print(f"  ↓ Deterministic miss (shot {shot}/6)")
                continue
        
        # Shots 3-4: Gemini Flash with targeted prompt
        if shot < 4:
            print(f"  💡 Flash fallback (shot {shot + 1}/6)")
            screenshot = await _screenshot(page, debug_dir, f"step_{step:02d}")
            try:
                action = await gemini_decide(screenshot, dom, profile, use_pro=False)
                print(f"  🤖 Flash → {json.dumps(action)[:120]}")
                ok = await execute_action(page, action, docx_path)
                log("apply_step_log", {
                    "step_num": step, "url": url,
                    "tier": "flash", "success": ok,
                    "action": action
                })
                if ok:
                    shot = 0
                    apply_smartapply._shot = 0
                    await asyncio.sleep(0.5)
                    continue
            except Exception as e:
                print(f"  ⚠️ Flash error: {e}")
            
            shot += 1
            apply_smartapply._shot = shot
            continue
        
        # Shots 5-6: Gemini Pro
        if shot < 6:
            print(f"  🧠 Pro fallback (shot {shot + 1}/6)")
            screenshot = await _screenshot(page, debug_dir, f"step_{step:02d}")
            try:
                action = await gemini_decide(screenshot, dom, profile, use_pro=True)
                print(f"  🤖 Pro → {json.dumps(action)[:120]}")
                ok = await execute_action(page, action, docx_path)
                log("apply_step_log", {
                    "step_num": step, "url": url,
                    "tier": "pro", "success": ok,
                    "action": action,
                    "dom_snapshot": dom if not ok else None
                })
                if ok:
                    shot = 0
                    apply_smartapply._shot = 0
                    await asyncio.sleep(0.5)
                    continue
            except Exception as e:
                print(f"  ⚠️ Pro error: {e}")
            
            shot += 1
            apply_smartapply._shot = shot
            continue
        
        # All 6 shots failed on this page — log and fail
        log("apply_step_log", {
            "step_num": step, "url": url,
            "tier": "exhausted", "success": False,
            "dom_snapshot": dom,
            "error_msg": "6 shots exhausted"
        })
        return {
            "status": "failed",
            "reason": f"6 shots exhausted at step {step} — likely new pattern"
        }
    
    return {"status": "failed", "reason": "Exceeded 50 steps without submission"}
```

**~150 lines.**

---

## Step 9: Modify `src/playwright_indeed.py`

### Changes:
1. **Remove** `_gemini_loop`, `_gemini_loop_inner` (L1147-1274) — replaced by router
2. **Remove** `_GEMINI_PROMPT` (L170-268) — replaced by targeted prompts
3. **Remove** `_gemini_decide()` (L270-340) — moved to gemini_fallback.py
4. **Move** `_execute()` (L344-635) — moved to smartapply/execute.py
5. **Keep** everything from L1-169 and L636-1146
6. **Change** L1131: `return await _gemini_loop(...)` → `return await apply_smartapply(...)`
7. **Add import**: `from smartapply import apply_smartapply`

### After trimming:
- L1-169: imports, config, profiles, AdsPower, human timing, screenshot (KEEP)
- L636-1146: CF bypass, warmup, URL routing, apply_to_job entry point (KEEP)
- Total: **~680 lines** (down from 1275)

---

## Step 10: Supabase Tables

Run SQL to create 3 tables:
- `apply_runs`
- `apply_step_log`  
- `apply_patterns`

(Schema from brainstorm doc `07_dom_first_architecture.md`)

---

## Execution Order

```
1. Create src/smartapply/ directory + __init__.py
2. Create dom_scanner.py
3. Create patterns.py
4. Create handlers.py
5. Create gemini_fallback.py
6. Create logger.py
7. Move _execute() → execute.py
8. Create router.py
9. Trim playwright_indeed.py (remove old loop, add import)
10. Create Supabase tables
11. Syntax check all files
12. Run test against same job URL
```

---

## What We DON'T Touch

- AdsPower lifecycle
- Stealth init script
- CF detection/bypass
- Human warmup
- Tab management
- Profile caching
- The `_execute()` internals (just moved, not changed)
