"""
Indeed apply automation — playwright + Gemini Vision.

Connects to AdsPower browser via CDP (port 30025 VPS).
Gemini Vision looks at each screenshot and decides the next action.
No hardcoded selectors — the AI navigates the form.

Interface (same as nodriver_indeed):
    result = await apply_to_job(apply_url, docx_path, user_id)
    # result = {"status": "success"|"failed"|"skipped"|"disqualified", "reason": "..."}
"""
import asyncio
import json
import os
os.environ["REBROWSER_PATCHES_RUNTIME_FIX_MODE"] = "addBinding"
import random
import re
import time
from datetime import datetime, timezone

import requests
import websockets
from dotenv import load_dotenv
from rebrowser_playwright.async_api import async_playwright, Browser, Page

# Load .env from the indeed-pipeline directory (override=True so it wins over
# any env vars pre-loaded by the IDE from parent .env files)
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_ENV_PATH, override=True)

# ── Supabase config ───────────────────────────────────────────────────────────
_SB_URL  = os.getenv("SUPABASE_URL", "")
_SB_KEY  = os.getenv("SUPABASE_KEY", "")
_SB_HDRS = {
    "apikey": _SB_KEY,
    "Authorization": f"Bearer {_SB_KEY}",
    "Content-Type": "application/json",
}

# ── Config ────────────────────────────────────────────────────────────────────
ADSPOWER_BASE    = os.getenv("ADSPOWER_BASE", "http://127.0.0.1:30025")
ADSPOWER_API_KEY = os.getenv("ADSPOWER_API_KEY")  # required — set in .env
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL     = "gemini-2.5-flash"            # fast — normal steps
GEMINI_MODEL_PRO = "gemini-3.1-pro-preview"      # smart — escalation when stuck
RUN_MODE         = os.getenv("RUN_MODE", "local")  # local | vps
DEBUG_DIR_BASE   = "/tmp/playwright_debug"

# ── Per-profile data from Supabase ────────────────────────────────────────────
# Fetched once at module load; keyed by user_id.
def _load_profiles() -> dict[str, dict]:
    if not _SB_URL or not _SB_KEY:
        print("[playwright] WARNING: SUPABASE_URL/KEY not set — profile cache empty")
        return {}
    try:
        r = requests.get(
            f"{_SB_URL}/rest/v1/adspower_profiles",
            params={"select": "*"},
            headers=_SB_HDRS,
            timeout=15,
        )
        r.raise_for_status()
        rows = r.json()
        cache = {row["user_id"]: row for row in rows}
        print(f"[playwright] Loaded {len(cache)} profiles from Supabase")
        return cache
    except Exception as e:
        print(f"[playwright] WARNING: Failed to load profiles from Supabase: {e}")
        return {}

_PROFILES: dict[str, dict] = _load_profiles()


def _patch_profile(user_id: str, data: dict):
    try:
        requests.patch(
            f"{_SB_URL}/rest/v1/adspower_profiles",
            params={"user_id": f"eq.{user_id}"},
            json=data,
            headers={**_SB_HDRS, "Prefer": "return=minimal"},
            timeout=10,
        )
    except Exception as e:
        print(f"  [supabase] patch_profile error: {e}")


def _cf_stonewalled(user_id: str):
    """Mark profile stone_walled in DB and in the in-memory cache."""
    now = datetime.now(timezone.utc).isoformat()
    _patch_profile(user_id, {
        "stone_walled": True,
        "stone_walled_at": now,
        "last_cf_hit": now,
        "risk_level": "hot",
    })
    if user_id in _PROFILES:
        _PROFILES[user_id]["stone_walled"] = True
        _PROFILES[user_id]["stone_walled_at"] = now
    # Telegram alert
    try:
        tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")
        if tg_token and tg_chat:
            name = _PROFILES.get(user_id, {}).get("full_name", user_id)
            requests.post(
                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                json={"chat_id": int(tg_chat), "text": f"🧱 STONEWALLED: {name} ({user_id})\nCF challenge failed 6x — profile paused.\nPipeline continues with other profiles.\nClean manually then tell me to clear it."},
                timeout=5,
            )
    except Exception:
        pass  # never block pipeline for a notification


# ── AdsPower helpers ─────────────────────────────────────────────────────────
def _cdp_alive(port) -> bool:
    """Check if CDP debug port is actually responding."""
    try:
        r = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _start_profile(user_id: str, _retries: int = 2) -> dict:
    """Start AdsPower profile & verify CDP port is alive. Retry if dead."""
    for attempt in range(_retries + 1):
        # If already active, check if port is alive
        try:
            r = requests.get(f"{ADSPOWER_BASE}/api/v1/browser/active",
                             params={"user_id": user_id, "api_key": ADSPOWER_API_KEY}, timeout=10)
            d = r.json()
            if d.get("code") == 0 and d.get("data", {}).get("status") == "Active":
                port = d["data"].get("debug_port", "?")
                if _cdp_alive(port):
                    print(f"[playwright] Profile already active on port {port}")
                    return d["data"]
                else:
                    print(f"[playwright] ⚠️  Port {port} dead — stopping stale profile")
                    _stop_profile(user_id)
                    time.sleep(3)
        except Exception:
            pass

        # Start fresh
        r = requests.get(f"{ADSPOWER_BASE}/api/v1/browser/start",
                         params={"user_id": user_id, "api_key": ADSPOWER_API_KEY}, timeout=60)
        r.raise_for_status()
        d = r.json()
        if d.get("code") != 0:
            raise RuntimeError(f"AdsPower start failed: {d}")
        port = d["data"].get("debug_port", "?")

        # Verify CDP is alive
        time.sleep(2)  # give browser a moment to boot
        if _cdp_alive(port):
            print(f"[playwright] Started on debug port {port} (CDP verified ✅)")
            return d["data"]

        print(f"[playwright] ⚠️  Port {port} not responding (attempt {attempt + 1}/{_retries + 1})")
        _stop_profile(user_id)
        time.sleep(3)

    raise RuntimeError(f"AdsPower profile {user_id} — CDP port dead after {_retries + 1} attempts")


def _stop_profile(user_id: str):
    try:
        requests.get(
            f"{ADSPOWER_BASE}/api/v1/browser/stop",
            params={"user_id": user_id, "api_key": ADSPOWER_API_KEY},
            timeout=10,
        )
    except Exception:
        pass


async def _kill_service_workers(ws_url: str):
    """Kill extension service workers & blank open tabs before Playwright attaches.

    AdsPower profiles with browsing history have Chrome extension SWs that
    deadlock rebrowser_playwright's addBinding patch during connect_over_cdp.
    Raw CDP can kill them safely — SWs auto-restart when needed later.
    """
    try:
        async with websockets.connect(ws_url, open_timeout=10) as ws:
            cmd_id = 1

            async def _send(method, params={}):
                nonlocal cmd_id
                await ws.send(json.dumps({"id": cmd_id, "method": method, "params": params}))
                cmd_id += 1
                while True:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                    if msg.get("id") == cmd_id - 1:
                        return msg.get("result", {})

            result = await _send("Target.getTargets")
            targets = result.get("targetInfos", [])

            sw_killed = 0
            for t in targets:
                if t["type"] == "service_worker":
                    await _send("Target.closeTarget", {"targetId": t["targetId"]})
                    sw_killed += 1

            for t in targets:
                if t["type"] == "page":
                    try:
                        r = await _send("Target.attachToTarget",
                                        {"targetId": t["targetId"], "flatten": True})
                        sid = r.get("sessionId")
                        if sid:
                            await ws.send(json.dumps({
                                "id": cmd_id, "method": "Page.navigate",
                                "params": {"url": "about:blank"}, "sessionId": sid
                            }))
                            cmd_id += 1
                    except Exception:
                        pass

            if sw_killed:
                print(f"[playwright] Killed {sw_killed} service worker(s) before CDP connect")
            await asyncio.sleep(1.0)
    except Exception as e:
        print(f"[playwright] ⚠️  SW cleanup skipped: {e}")


# ── Human timing ──────────────────────────────────────────────────────────────
async def _delay(min_s: float, max_s: float):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _human_type(locator, text: str):
    await locator.click()
    await _delay(0.2, 0.5)
    for char in text:
        await locator.press(char)
        await asyncio.sleep(random.uniform(0.05, 0.18))


async def human_scroll(page: Page, total_pixels: int = 400):
    """Trusted WheelEvents via CDP — replaces window.scrollBy (which produces no WheelEvents)."""
    remaining = total_pixels
    while abs(remaining) > 0:
        step = max(60, min(220, int(abs(random.gauss(140, 40)))))
        step = min(step, abs(remaining))
        delta = step if remaining > 0 else -step
        await page.mouse.wheel(0, delta)
        remaining -= delta
        await asyncio.sleep(random.uniform(0.05, 0.25))
        if random.random() < 0.15:
            await asyncio.sleep(random.uniform(0.3, 1.2))


# ── Screenshot ────────────────────────────────────────────────────────────────
async def _screenshot(page: Page, debug_dir: str, label: str, full_page: bool = False) -> bytes:
    import base64
    os.makedirs(debug_dir, exist_ok=True)
    path = os.path.join(debug_dir, f"{label}.jpg")
    try:
        if not full_page:
            # Bypass Playwright's high-level checks (like waiting for fonts/animations)
            # which randomly cause renderer hangs in AdsPower.
            client = await page.context.new_cdp_session(page)
            try:
                res = await asyncio.wait_for(
                    client.send("Page.captureScreenshot", {"format": "jpeg", "quality": 50}),
                    timeout=10.0
                )
                data = base64.b64decode(res["data"])
            finally:
                await client.detach()
        else:
            data = await page.screenshot(
                full_page=True, 
                type="jpeg", 
                quality=50,
                timeout=15000
            )

        with open(path, "wb") as f:
            f.write(data)
            
        print(f"  📸 {label}.jpg ({len(data)//1024}KB)")
        return data
    except Exception as e:
        print(f"  ⚠️ Screenshot failed: {e}")
        raise e


# ── Gemini Vision ─────────────────────────────────────────────────────────────
_GEMINI_PROMPT = """\
You are controlling a browser to submit a job application.
Platform: {platform}

APPLICANT INFO — use this to fill any form fields:
  Name:              {name}
  Email:             {email}
  Phone:             {phone}
  Years experience:  {years_exp}
  Education:         {education}
  Hourly wage:       {salary_hr}
  Annual salary:     {salary_yr}

CURRENT URL: {url}
STEP: {step}/50

PAGE SCANNING STRATEGY — do this EVERY step:
  1. SCAN the entire visible page from top to bottom
  2. IDENTIFY all interactive elements: questions, inputs, radios, dropdowns, buttons
  3. DETERMINE which elements are UNANSWERED or UNSELECTED (look for empty radios ○, unselected options, blank fields, error messages like "Choose an option" or "Required")
  4. ACT on the FIRST unanswered/incomplete element from top to bottom
  5. Only click "Continue" / "Next" / "Submit" AFTER all visible questions are answered

Look at the screenshot. Choose the SINGLE NEXT ACTION to move toward submitting the application.

Reply with ONLY a valid JSON object — no markdown, no explanation outside the JSON:
{{
  "action": "click|fill|select_option|check|scroll|upload|done|failed|skip",
  "target": "exact visible text of the button / label / card / field to interact with",
  "value":  "text to type or option label (fill and select_option only)",
  "reason": "one-line explanation"
}}

ACTION RULES:
  done          → you see "Application submitted", "You applied", "Thank you for applying", or a clear success screen
  failed        → stuck on an unrecoverable error screen (login wall, etc.) — NOT for Cloudflare/Turnstile (those are handled automatically)
  skip          → ONLY an external "Apply on company site" button exists and no form is present
  scroll        → no interactive target visible yet; need to scroll to reveal it
  upload        → file input visible and ready for a file
  click         → tap a button, radio label, card, link, or any selectable card/tile
  fill          → type into a text/number/textarea input (autocomplete suggestions are handled automatically — do NOT do a separate click to select them)
  select_option → pick from a dropdown (native <select> OR custom styled dropdown)
  check         → toggle a checkbox (target = the checkbox label text)

CRITICAL — DUPLICATE LABELS:
  Many pages have MULTIPLE questions with identical radio labels (e.g., two "Yes"/"No" groups).
  When this happens:
  • Look for UNANSWERED questions — they have EMPTY radio circles (○ not ●)
  • The target must include CONTEXT from the question text, not just "Yes" or "No"
  • Example: if the page has two Yes/No questions and the second is unanswered, use:
    {{"action": "click", "target": "relocate Yes", "reason": "answering relocation question"}}
    or include part of the question text near the radio button
  • A FILLED radio (●) means that question is ALREADY answered — skip it
  • If there is a red error message like "Choose an option to continue", that question MUST be answered

SAFETY RULES:
  • NEVER try to change/edit the resume, even if the name on it (Oswaldo Lara) doesn't match the applicant. Ignore mismatch and just submit.
  • NEVER interact with hidden, disabled, invisible, zero-size, or off-screen elements
  • NEVER fill fields labeled "do not fill", "leave blank", or similar
  • NEVER click "Save and close" — ignore it; scroll down to find "Continue" or "Submit"
  • If you see the same page twice in a row, try a DIFFERENT action than last time
  • Do NOT click Sign In / Login — we are already authenticated
  • Do NOT click "Edit" on the resume section or any section on the review page.
  • Do NOT re-click a radio that is already selected (filled circle ●)

FORM TYPE GUIDANCE:
  • Boolean question (Yes/No)     → use click on the correct radio label. Include question context in target.
  • Enum / multiple choice        → use click on the card/label, or select_option for <select>
  • Free text / number            → use fill
  • Checkbox                      → use check
  • Native <select> dropdown      → use select_option (target = label text near dropdown, value = option to select)
  • Custom styled dropdown        → use select_option (same — executor handles both)
  • Date range / availability     → use select_option or click the appropriate option/checkbox
  • Interview availability        → select earliest / "Within 1 week" / "Immediately" or similar

SPECIFIC CHOICES:
  {resume_instruction}
  • NEVER try to change/edit the resume, even if the name on it (Oswaldo Lara) doesn't match the applicant. Ignore mismatch and just submit/continue.
  • Yes/No radio groups           → click "Yes" unless No is clearly more accurate. ALWAYS include question context in target.
  • Education level               → "High School Diploma" or "Bachelor's Degree"
  • Employment type               → "Full-time"
  • Salary / wage fields          → hourly {salary_hr} or annual {salary_yr}
  • Settings page URL (/settings) → action = "failed"
  • Phone number field            → {phone_instruction}
  • Country / country-code field  → if already showing "United States" or "+1", skip it and click Continue instead
  • Any field already filled correctly → do NOT re-fill; move to the next unanswered field or click Continue
  • Start date / availability     → "Immediately" or the earliest option available
  • Schedule / shift preference   → select all available or "Any"
  • If a field has no provided data and is optional → skip it and click Continue
  • If a field has no provided data and is required → use a reasonable default (e.g., "3" for years, "Full-time" for type)

MULTI-SLOT QUESTIONS (e.g., "interview availability" with multiple Day/Time rows):
  • Fill the FIRST row only (one Day + one Time is sufficient)
  • If there are extra empty rows with a "−" (minus/remove) button next to them, click the minus to REMOVE the empty row
  • Then click Continue
  • Do NOT try to fill every optional slot

EFFICIENCY:
  • After answering all visible questions, click Continue IMMEDIATELY
  • Do not scroll around looking for more content after answering — go straight to Continue
  • If Continue is visible and all questions are answered, click it — don't scroll first
"""


async def _gemini_decide(screenshot_bytes: bytes, url: str, step: int, profile: dict, model_override: str = None) -> dict:
    from google import genai
    from google.genai import types

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY env var is not set")

    model = model_override or GEMINI_MODEL
    client = genai.Client(api_key=GEMINI_API_KEY)

    is_external = profile.get("is_external", False)
    platform = profile.get("platform", "Indeed SmartApply")

    if is_external:
        resume_instruction = (
            '• Resume upload      → use upload action when a file input appears'
            if profile.get("has_resume")
            else '• Resume upload      → skip if asked; fill in experience manually'
        )
    else:
        resume_instruction = (
            '• Resume choice screen → click "Upload a resume" (not "Build an Indeed Resume")'
            if profile.get("has_resume")
            else '• Resume choice screen → click "Build an Indeed Resume" (no file to upload)'
        )

    phone = profile.get("phone", "")
    if phone and phone != "None":
        phone_instruction = f"fill with {phone} (include country code if needed)"
    else:
        phone_instruction = "no phone number in our records — if the field already has a number pre-filled, leave it as-is and click Continue. Do NOT clear or overwrite it."

    prompt = _GEMINI_PROMPT.format(
        platform=platform,
        name=profile.get("name", ""),
        email=profile.get("email", ""),
        phone=phone if phone and phone != "None" else "(not provided)",
        years_exp=profile.get("years_exp", "3"),
        education=profile.get("education", "High School Diploma"),
        salary_hr=profile.get("salary_hr", "25"),
        salary_yr=profile.get("salary_yr", "52000"),
        url=url,
        step=step,
        resume_instruction=resume_instruction,
        phone_instruction=phone_instruction,
    )

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(data=screenshot_bytes, mime_type="image/png"),
        ],
    )

    raw = response.text.strip()
    print(f"  🤖 Gemini → {raw[:200]}")

    # Strip markdown fences if Gemini wrapped the JSON
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw.strip())
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'\{.*?\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise ValueError(f"Could not parse Gemini response as JSON: {raw[:300]}")


# ── Action executor ───────────────────────────────────────────────────────────
async def _execute(page: Page, action: dict, docx_path: str | None) -> bool:
    """Execute a Gemini-decided action. Returns True if something was done."""
    act    = action.get("action", "")
    target = action.get("target", "")
    value  = action.get("value", "")

    if act == "scroll":
        await human_scroll(page)
        return True

    if act == "upload":
        if not docx_path or not os.path.exists(docx_path):
            print("  ⚠️  upload requested but file not available")
            return False
        await page.locator("input[type='file']").first.set_input_files(docx_path)
        await asyncio.sleep(1)  # wait for upload to register
        return True

    if act == "click":
        strategies = [
            page.get_by_role("button",  name=target, exact=False),
            page.get_by_role("link",    name=target, exact=False),
            page.get_by_role("radio",   name=target, exact=False),
            page.get_by_role("option",  name=target, exact=False),
            page.get_by_label(target,   exact=False),
            page.get_by_text(target,    exact=True),
            page.get_by_text(target,    exact=False),
            page.locator(f"label:has-text('{target}')"),
            page.locator(f"[role='radio']:has-text('{target}')"),
            page.locator(f"article:has-text('{target}')"),
            page.locator(f"div[data-testid]:has-text('{target}')"),
        ]
        for loc in strategies:
            try:
                el = loc.first
                await el.wait_for(state="visible", timeout=2000)
                await el.scroll_into_view_if_needed()
                await el.click()
                await asyncio.sleep(0.3)
                return True
            except Exception:
                continue

        # Smart radio fallback: Gemini sends "speak Spanish Yes" but radio is just "Yes"
        # under question "Do you speak Spanish?" — find question → click answer within it
        try:
            clicked_selector = await page.evaluate(f"""() => {{
                const target = {json.dumps(target.lower())};
                // Common answer words that Gemini appends to question text
                const answers = ['yes', 'no', "doesn't apply", "doesn't apply"];
                let questionPart = target;
                let answerPart = null;
                for (const a of answers) {{
                    if (target.endsWith(' ' + a)) {{
                        questionPart = target.slice(0, -(a.length + 1)).trim();
                        answerPart = a;
                        break;
                    }}
                }}
                if (!answerPart) {{
                    // Try splitting on last space as fallback
                    const parts = target.split(/\\s+/);
                    if (parts.length >= 2) {{
                        answerPart = parts[parts.length - 1];
                        questionPart = parts.slice(0, -1).join(' ');
                    }}
                }}
                if (!answerPart) return null;

                // Find all text nodes containing the question
                const allElements = document.querySelectorAll('legend, label, span, p, div');
                for (const el of allElements) {{
                    const text = el.textContent.toLowerCase().trim();
                    if (!text.includes(questionPart)) continue;
                    // Found question — look for radio/label with answer within parent container
                    const container = el.closest('fieldset') || el.closest('[role="radiogroup"]') || el.parentElement?.parentElement;
                    if (!container) continue;
                    // Try marking label with answer text
                    const labels = container.querySelectorAll('label, [role="radio"], input[type="radio"]');
                    for (const lbl of labels) {{
                        if (lbl.textContent.toLowerCase().trim() === answerPart ||
                            lbl.textContent.toLowerCase().includes(answerPart)) {{
                            lbl.setAttribute('data-gemini-target', 'true');
                            return 'lbl1';
                        }}
                        // For input[type=radio], check sibling label
                        if (lbl.tagName === 'INPUT') {{
                            const sibLabel = lbl.labels?.[0] || lbl.nextElementSibling;
                            if (sibLabel && sibLabel.textContent.toLowerCase().includes(answerPart)) {{
                                sibLabel.setAttribute('data-gemini-target', 'true');
                                return 'lbl2';
                            }}
                        }}
                    }}
                }}
                return null;
            }}""")
            if clicked_selector:
                try:
                    el = page.locator('[data-gemini-target="true"]').first
                    await el.click(force=True)
                    # clean up
                    await page.evaluate("""() => {
                        document.querySelectorAll('[data-gemini-target]').forEach(e => e.removeAttribute('data-gemini-target'));
                    }""")
                    print(f"  ✓ radio fallback: '{target}'")
                    await asyncio.sleep(0.3)
                    return True
                except Exception as e:
                    pass
        except Exception:
            pass

        print(f"  ⚠️  click: element not found — '{target}'")
        return False

    if act == "fill":
        strategies = [
            page.get_by_label(target,       exact=False),
            page.get_by_placeholder(target, exact=False),
        ]
        for loc in strategies:
            try:
                el = loc.first
                await el.wait_for(state="visible", timeout=2000)
                await el.clear()
                await _human_type(el, value)
                # Auto-commit autocomplete
                for autocomplete_sel in [
                    "[role='option']:visible",
                    "[role='listbox'] [role='option']:visible",
                    "ul[role='listbox'] li:visible",
                    ".autocomplete__option:visible",
                    "[data-testid*='suggestion']:visible",
                ]:
                    try:
                        suggestion = page.locator(autocomplete_sel).first
                        await suggestion.wait_for(state="visible", timeout=800)
                        await suggestion.click()
                        break
                    except Exception:
                        continue
                return True
            except Exception:
                continue
        print(f"  ⚠️  fill: field not found — '{target}'")
        return False

    if act == "select_option":
        # Smart dropdown handler: read actual options, fuzzy match
        # 1. JS-first approach — read all selects + their options, fuzzy match
        try:
            result = await page.evaluate(f"""() => {{
                const selects = Array.from(document.querySelectorAll('select'));
                const label_text = {json.dumps(target.lower())};
                const want = {json.dumps(value.lower())};
                for (const sel of selects) {{
                    const id = sel.id;
                    const lbl = id ? document.querySelector('label[for="' + id + '"]') : null;
                    const lblText = (lbl ? lbl.textContent : '').toLowerCase();
                    const ariaLabel = (sel.getAttribute('aria-label') || '').toLowerCase();
                    const name = (sel.getAttribute('name') || '').toLowerCase();
                    // Match by label, aria-label, or name
                    const matches = lblText.includes(label_text) || ariaLabel.includes(label_text) || name.includes(label_text);
                    if (!matches && selects.length > 1) continue;
                    // Get all options
                    const opts = Array.from(sel.options).filter(o => o.value && o.value !== '');
                    // Exact match first
                    let opt = opts.find(o => o.text.toLowerCase() === want);
                    // Then substring match
                    if (!opt) opt = opts.find(o => o.text.toLowerCase().includes(want) || want.includes(o.text.toLowerCase()));
                    // Then word overlap match
                    if (!opt) {{
                        const wantWords = want.split(/\s+/);
                        opt = opts.find(o => {{
                            const oWords = o.text.toLowerCase().split(/\s+/);
                            return wantWords.some(w => oWords.some(ow => ow.includes(w) || w.includes(ow)));
                        }});
                    }}
                    // Last resort: pick first non-empty option
                    if (!opt && opts.length > 0) opt = opts[0];
                    if (opt) {{
                        sel.value = opt.value;
                        sel.dispatchEvent(new Event('change', {{bubbles: true}}));
                        sel.dispatchEvent(new Event('input',  {{bubbles: true}}));
                        return opt.text;
                    }}
                }}
                return null;
            }}""")
            if result:
                print(f"  ✓ select_option: picked '{result}'")
                await _delay(0.2, 0.4)
                return True
        except Exception:
            pass

        # 2. Playwright native select
        native_locs = [
            page.get_by_label(target, exact=False),
            page.locator(f"select[aria-label*='{target}' i]"),
        ]
        for loc in native_locs:
            try:
                el = loc.first
                await el.wait_for(state="attached", timeout=1000)
                await el.select_option(label=value)
                await _delay(0.2, 0.4)
                return True
            except Exception:
                continue

        # 2. Custom styled dropdown — click the trigger, then click the option
        target_lower = target.lower()
        trigger_strategies = [
            page.get_by_label(target,                       exact=False),
            page.get_by_role("combobox",                    name=target, exact=False),
            page.get_by_text(target,                        exact=True),
            page.locator(f"[aria-label*='{target}']"),
            page.locator(f"[placeholder*='{target}']"),
            page.locator(f"[aria-haspopup='listbox']:has-text('{target}')"),
            page.locator("[aria-haspopup='listbox']").first,
            page.locator("[aria-haspopup='true']").first,
            # Phone country-code flag button (Indeed uses a <button> before the phone input)
            page.locator("button[class*='phone']"),
            page.locator("button[data-testid*='phone']"),
            page.locator("button[aria-label*='country' i]"),
            page.locator("button[aria-label*='Country' i]"),
            page.locator("[class*='PhoneInputCountrySelect']").first,
            page.locator("[class*='phoneCountry']").first,
            page.locator("[class*='country-selector']").first,
        ]

        for loc in trigger_strategies:
            try:
                trigger = loc.first
                await trigger.wait_for(state="visible", timeout=1000)
                await trigger.click()
                await _delay(0.5, 1.0)

                # After opening the dropdown, try to type to filter (for long country lists)
                search_typed = False
                try:
                    search_box = page.locator("[role='listbox'] input, [role='dialog'] input, input[placeholder*='search' i]").first
                    await search_box.wait_for(state="visible", timeout=600)
                    await search_box.type(value[:8], delay=60)
                    await _delay(0.3, 0.6)
                    search_typed = True
                except Exception:
                    pass

                for opt_sel in [
                    page.get_by_role("option",  name=value, exact=False),
                    page.get_by_role("option",  name=value, exact=True),
                    page.locator(f"[role='option']:has-text('{value}')"),
                    page.locator(f"[role='listbox'] li:has-text('{value}')"),
                    page.locator(f"li:has-text('{value}')"),
                ]:
                    try:
                        opt = opt_sel.first
                        await opt.wait_for(state="visible", timeout=1500)
                        await opt.click()
                        await _delay(0.3, 0.6)
                        return True
                    except Exception:
                        continue

                # Couldn't click the option — close the dropdown and try next trigger
                try:
                    await page.keyboard.press("Escape")
                    await _delay(0.2, 0.4)
                except Exception:
                    pass
            except Exception:
                continue

        print(f"  ⚠️  select_option: not found — '{target}' / '{value}'")
        return False

    if act == "check":
        strategies = [
            page.get_by_label(target,           exact=False),
            page.get_by_role("checkbox",        name=target, exact=False),
            page.locator(f"label:has-text('{target}') input[type='checkbox']"),
            page.locator(f"[aria-label*='{target}'][type='checkbox']"),
        ]
        for loc in strategies:
            try:
                el = loc.first
                await el.wait_for(state="visible", timeout=2000)
                await el.scroll_into_view_if_needed()
                await _delay(0.2, 0.5)
                await el.check()
                await _delay(0.3, 0.6)
                return True
            except Exception:
                continue
        # Fallback: external ATS custom checkboxes (div/span with click handler)
        click_strategies = [
            page.get_by_text(target, exact=False).first,
            page.locator(f"[role='switch']:near(:text('{target}'))").first,
            page.locator(f"[role='option']:has-text('{target}')").first,
            page.locator(f"label:has-text('{target}')").first,
        ]
        for loc in click_strategies:
            try:
                await loc.wait_for(state="visible", timeout=2000)
                await loc.scroll_into_view_if_needed()
                await _delay(0.2, 0.5)
                await loc.click()
                await _delay(0.3, 0.6)
                print(f"  ✓ check (click fallback): '{target}'")
                return True
            except Exception:
                continue
        print(f"  ⚠️  check: checkbox not found — '{target}'")
        return False

    return False


# ── Cloudflare detection & bypass ─────────────────────────────────────────────
async def _is_cf(page: Page) -> bool:
    """Detect any Cloudflare challenge page — title check + DOM script check."""
    title = (await page.title()).lower()
    if any(s in title for s in [
        "just a moment", "attention required", "security check",
        "additional verification", "verify you are human",
    ]):
        return True
    # Check for CF scripts in the DOM (catches invisible Turnstile too)
    try:
        has_cf = await page.evaluate("""() => {
            const scripts = [...document.querySelectorAll('script[src]')].map(s => s.src);
            return scripts.some(u =>
                u.includes('challenges.cloudflare.com') ||
                u.includes('cdn-cgi/challenge-platform') ||
                u.includes('turnstile/v0/api.js')
            );
        }""")
        return has_cf
    except Exception:
        return False


async def _bypass_cf(page: Page, max_retries: int = 8) -> bool:
    """
    Attempt to bypass Cloudflare Turnstile by finding the challenge iframe
    and clicking it with human-like Bezier mouse movement.
    Returns True if CF is gone, False if still stuck.
    """
    for attempt in range(1, max_retries + 1):
        if not await _is_cf(page):
            print(f"  ✓ CF cleared (attempt {attempt})")
            return True

        print(f"  [cf-bypass] attempt {attempt}/{max_retries}")

        # Find CF iframe (Turnstile checkbox lives inside an iframe)
        iframe_locator = None
        for selector in [
            "iframe[src*='challenges.cloudflare.com']",
            "iframe[src*='turnstile']",
            "iframe[id*='cf-']",
            "iframe[class*='cf-']",
            "iframe[title*='challenge']",
        ]:
            try:
                loc = page.locator(selector).first
                if await loc.is_visible(timeout=1000):
                    iframe_locator = loc
                    break
            except Exception:
                continue

        if iframe_locator:
            try:
                box = await iframe_locator.bounding_box()
                if box:
                    # Click near center of the iframe with human mouse movement
                    cx = box["x"] + box["width"] * random.uniform(0.3, 0.7)
                    cy = box["y"] + box["height"] * random.uniform(0.3, 0.7)

                    # Bezier curve mouse movement to target
                    current = await page.evaluate("() => ({x: 0, y: 0})")
                    steps = random.randint(15, 30)
                    for i in range(1, steps + 1):
                        t = i / steps
                        # Cubic ease-in-out with slight randomness
                        t2 = t * t * (3 - 2 * t)
                        mx = current.get("x", 0) + (cx - current.get("x", 0)) * t2 + random.uniform(-2, 2)
                        my = current.get("y", 0) + (cy - current.get("y", 0)) * t2 + random.uniform(-2, 2)
                        await page.mouse.move(mx, my)
                        await asyncio.sleep(random.uniform(0.008, 0.025))

                    await asyncio.sleep(random.uniform(0.1, 0.3))
                    await page.mouse.click(cx, cy)
                    print(f"  [cf-bypass] clicked iframe at ({cx:.0f}, {cy:.0f})")
            except Exception as e:
                print(f"  [cf-bypass] click error: {e}")
        else:
            # No iframe found — might be invisible Turnstile or JS challenge
            # Wait and let CF auto-resolve
            print(f"  [cf-bypass] no iframe found — waiting for auto-resolve")

        # Wait for CF to process the click
        await asyncio.sleep(random.uniform(3.0, 6.0))

        # Reload every 3 attempts if still stuck
        if attempt % 3 == 0 and await _is_cf(page):
            print(f"  [cf-bypass] reloading page")
            await page.reload(wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(random.uniform(2.0, 4.0))

    still_cf = await _is_cf(page)
    if not still_cf:
        print(f"  ✓ CF cleared after retries")
        return True
    print(f"  ✗ CF bypass failed after {max_retries} attempts")
    return False


async def _solve_cf(page: Page, debug_dir: str = "") -> bool:
    """
    CF Turnstile solver:
    1. Try 2Captcha Turnstile API (token injection — high success rate)
    2. Fall back to Gemini vision click (low success rate)
    """
    import re as _re

    # ── Step 1: Try 2Captcha Turnstile ────────────────────────────────────────
    print("[cf-solve] Attempting 2Captcha Turnstile solver...")
    key = os.getenv("TWOCAPTCHA_API_KEY", "")
    if key:
        solved = await _solve_cf_2captcha(page, key)
        if solved:
            return True
        print("[cf-solve] 2Captcha failed — falling back to Gemini click")

    # ── Step 2: Gemini vision fallback ────────────────────────────────────────
    from google import genai
    from google.genai import types

    CF_PROMPT = """You are looking at a Cloudflare Turnstile verification page.

Your ONLY job: find the checkbox/button to verify you are human.

Look for:
- A checkbox with text like "Verify you are human" or "I'm not a robot"  
- A button that says "Verify" or similar
- The Turnstile widget (usually a small box with a checkbox)

If you see such an element, respond with EXACTLY:
{"action": "click", "x": <center_x>, "y": <center_y>}

Where x,y are the pixel coordinates of the CENTER of the checkbox/button.

If the page shows "Verifying..." or is already processing, respond:
{"action": "wait"}

If you don't see any Turnstile/verification element, respond:
{"action": "none"}

Respond with ONLY the JSON, nothing else."""

    for attempt in range(1, 4):  # reduced from 6 → 3 since 2Captcha is primary
        if not await _is_cf(page):
            print(f"[cf-solve] ✓ CF cleared! (attempt {attempt})")
            return True

        print(f"[cf-solve] Gemini attempt {attempt}/3 — taking screenshot...")
        try:
            ss_bytes = await page.screenshot(type="jpeg", quality=80, animations="disabled", timeout=15000)
        except Exception as e:
            print(f"  [cf-solve] ⚠️ screenshot failed: {e}")
            await asyncio.sleep(2)
            continue
        if debug_dir:
            ss_path = f"{debug_dir}/cf_solve_{attempt}.jpg"
            os.makedirs(debug_dir, exist_ok=True)
            with open(ss_path, "wb") as f:
                f.write(ss_bytes)

        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            resp = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(data=ss_bytes, mime_type="image/jpeg"),
                    CF_PROMPT,
                ],
            )
            raw = resp.text.strip()
            import json as _json
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            action = _json.loads(raw)
            print(f"[cf-solve] Gemini says: {action}")

            if action.get("action") == "click":
                cx = float(action["x"])
                cy = float(action["y"])
                start_x = random.uniform(100, 400)
                start_y = random.uniform(100, 300)
                await page.mouse.move(start_x, start_y)
                await asyncio.sleep(random.uniform(0.2, 0.5))
                steps = random.randint(20, 35)
                for i in range(1, steps + 1):
                    t = i / steps
                    t2 = t * t * (3 - 2 * t)
                    mx = start_x + (cx - start_x) * t2 + random.uniform(-1.5, 1.5)
                    my = start_y + (cy - start_y) * t2 + random.uniform(-1.5, 1.5)
                    await page.mouse.move(mx, my)
                    await asyncio.sleep(random.uniform(0.008, 0.02))
                await asyncio.sleep(random.uniform(0.15, 0.4))
                await page.mouse.click(cx, cy)
                print(f"[cf-solve] clicked ({cx:.0f}, {cy:.0f})")
                await asyncio.sleep(random.uniform(3.0, 5.0))
            elif action.get("action") == "wait":
                print("[cf-solve] Gemini says wait — CF is processing...")
                await asyncio.sleep(5)
            else:
                print("[cf-solve] Gemini didn't find checkbox — trying iframe fallback")
                await _bypass_cf(page, max_retries=2)
        except Exception as e:
            print(f"[cf-solve] Gemini error: {e} — trying iframe fallback")
            await _bypass_cf(page, max_retries=2)

        await asyncio.sleep(random.uniform(2.0, 4.0))

    still_cf = await _is_cf(page)
    if not still_cf:
        print("[cf-solve] ✓ CF cleared after retries!")
        return True
    print("[cf-solve] ✗ CF still present after all attempts")
    return False


async def _solve_cf_2captcha(page: Page, api_key: str) -> bool:
    """
    Solve CF Turnstile via 2Captcha token injection.
    1. Extract sitekey from DOM/frames
    2. Intercept turnstile params (cData, chlPageData, action) if possible
    3. Send to 2Captcha createTask API
    4. Inject token via turnstile callback
    """
    import re as _re

    # ── Extract sitekey ───────────────────────────────────────────────────────
    sitekey = await page.evaluate("""() => {
        // Method 1: data-sitekey attribute
        const el = document.querySelector('[data-sitekey]');
        if (el) return el.getAttribute('data-sitekey');
        // Method 2: from script/meta
        const html = document.documentElement.innerHTML;
        const m = html.match(/sitekey['"]?\\s*[:=]\\s*['"]([0-9x][A-Za-z0-9_-]{20,})['"]/);
        if (m) return m[1];
        return null;
    }""")

    # Method 3: from turnstile iframe URL
    if not sitekey:
        for frame in page.frames:
            if 'challenges.cloudflare.com' in frame.url:
                m = _re.search(r'[?&]k=([^&]+)', frame.url)
                if m:
                    sitekey = m.group(1)
                    break

    if not sitekey:
        print("  [cf-2captcha] ❌ No sitekey found")
        return False

    print(f"  [cf-2captcha] sitekey={sitekey[:20]}...")

    # ── Try to intercept turnstile params for CF Challenge pages ──────────────
    ts_params = await page.evaluate("""() => {
        try {
            const html = document.documentElement.innerHTML;
            const params = {};
            // Look for cData
            let m = html.match(/cData['"]?\\s*[:=]\\s*['"]([^'"]+)['"]/);
            if (m) params.data = m[1];
            // Look for chlPageData
            m = html.match(/chlPageData['"]?\\s*[:=]\\s*['"]([^'"]+)['"]/);
            if (m) params.pagedata = m[1];
            // Look for action
            m = html.match(/action['"]?\\s*[:=]\\s*['"](managed|interactive)['"]/);
            if (m) params.action = m[1];
            return Object.keys(params).length > 0 ? params : null;
        } catch(e) { return null; }
    }""")

    # ── Send to 2Captcha ──────────────────────────────────────────────────────
    import httpx
    async with httpx.AsyncClient(timeout=120) as client:
        task = {
            "type": "TurnstileTaskProxyless",
            "websiteURL": page.url,
            "websiteKey": sitekey,
        }
        if ts_params:
            task.update(ts_params)
            print(f"  [cf-2captcha] CF Challenge mode (has extra params)")
        else:
            print(f"  [cf-2captcha] Standalone Turnstile mode")

        # Submit task
        r = await client.post("https://api.2captcha.com/createTask", json={
            "clientKey": api_key,
            "task": task,
        })
        data = r.json()
        if data.get("errorId"):
            print(f"  [cf-2captcha] Submit error: {data.get('errorDescription', data)}")
            return False

        task_id = data.get("taskId")
        print(f"  [cf-2captcha] Task submitted: {task_id} — polling...")

        # Poll for result
        await asyncio.sleep(10)
        for i in range(24):  # max ~2 min
            r = await client.post("https://api.2captcha.com/getTaskResult", json={
                "clientKey": api_key,
                "taskId": task_id,
            })
            data = r.json()
            if data.get("status") == "ready":
                token = data["solution"]["token"]
                print(f"  [cf-2captcha] ✅ Solved in ~{10 + (i+1)*5}s")
                break
            if data.get("errorId"):
                print(f"  [cf-2captcha] Error: {data.get('errorDescription', data)}")
                return False
            await asyncio.sleep(5)
        else:
            print("  [cf-2captcha] ⏰ Timeout (2 min)")
            return False

    # ── Inject token ──────────────────────────────────────────────────────────
    await page.evaluate("""(token) => {
        // Set turnstile response inputs
        const inputs = document.querySelectorAll(
            '[name="cf-turnstile-response"], [name="g-recaptcha-response"]'
        );
        inputs.forEach(el => {
            const setter = Object.getOwnPropertyDescriptor(
                HTMLTextAreaElement.prototype, 'value'
            )?.set || Object.getOwnPropertyDescriptor(
                HTMLInputElement.prototype, 'value'
            )?.set;
            if (setter) setter.call(el, token);
            else el.value = token;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        });

        // Fire turnstile callback
        if (typeof window.tsCallback === 'function') {
            window.tsCallback(token);
        }

        // Try to find and fire the callback from turnstile internals
        try {
            if (window.turnstile) {
                // Submit form if exists (CF challenge pages auto-submit)
                const form = document.querySelector('#challenge-form, form');
                if (form) form.submit();
            }
        } catch(e) {}
    }""", token)

    await asyncio.sleep(4)

    if not await _is_cf(page):
        print("  [cf-2captcha] ✓ CF cleared after token injection!")
        return True

    # Token was injected but CF still showing — try submitting form
    try:
        await page.evaluate("""() => {
            const form = document.querySelector('#challenge-form, form');
            if (form) form.submit();
        }""")
        await asyncio.sleep(3)
        if not await _is_cf(page):
            print("  [cf-2captcha] ✓ CF cleared after form submit!")
            return True
    except Exception:
        pass

    print("  [cf-2captcha] ❌ Token injected but CF still present")
    return False


# ── reCAPTCHA detection & bypass ──────────────────────────────────────────────
async def _has_recaptcha(page: Page) -> bool:
    """Detect Google reCAPTCHA v2 on the page."""
    try:
        return await page.evaluate("""() => {
            return document.querySelector('iframe[src*="google.com/recaptcha"]') !== null
                || document.querySelector('.g-recaptcha') !== null
                || document.querySelector('[data-sitekey]') !== null;
        }""")
    except Exception:
        return False


async def _solve_recaptcha(page: Page) -> bool:
    """Click reCAPTCHA v2 checkbox using Bezier mouse movement.
    
    Same stealth pattern as _bypass_cf() — find iframe, calculate
    checkbox position, move mouse with human-like curve, click.
    """
    for attempt in range(1, 4):
        print(f"  [recaptcha] attempt {attempt}/3")

        # Find reCAPTCHA iframe
        iframe_loc = None
        for sel in [
            "iframe[src*='google.com/recaptcha']",
            "iframe[title*='reCAPTCHA']",
            "iframe[title*='recaptcha']",
        ]:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=2000):
                    iframe_loc = loc
                    break
            except Exception:
                continue

        if not iframe_loc:
            print(f"  [recaptcha] no iframe found")
            return False

        try:
            box = await iframe_loc.bounding_box()
            if not box:
                continue
            # reCAPTCHA checkbox is at left-center of the iframe
            # Standard iframe is ~304x78 — checkbox at roughly (28, center_y)
            cx = box["x"] + 28 + random.uniform(-3, 3)
            cy = box["y"] + (box["height"] / 2) + random.uniform(-3, 3)

            # Bezier mouse movement to checkbox
            start_x = random.uniform(200, 500)
            start_y = random.uniform(200, 400)
            await page.mouse.move(start_x, start_y)
            await asyncio.sleep(random.uniform(0.3, 0.6))

            steps = random.randint(20, 35)
            for i in range(1, steps + 1):
                t = i / steps
                t2 = t * t * (3 - 2 * t)  # cubic ease-in-out
                mx = start_x + (cx - start_x) * t2 + random.uniform(-1.5, 1.5)
                my = start_y + (cy - start_y) * t2 + random.uniform(-1.5, 1.5)
                await page.mouse.move(mx, my)
                await asyncio.sleep(random.uniform(0.008, 0.02))

            await asyncio.sleep(random.uniform(0.15, 0.4))
            await page.mouse.click(cx, cy)
            print(f"  [recaptcha] clicked checkbox ({cx:.0f}, {cy:.0f})")
            await asyncio.sleep(random.uniform(2.0, 4.0))

            # Check if reCAPTCHA is satisfied
            try:
                solved = await page.evaluate("""() => {
                    const resp = document.querySelector('#g-recaptcha-response, [name="g-recaptcha-response"], textarea[id*="recaptcha-response"]');
                    return resp && resp.value && resp.value.length > 0;
                }""")
                if solved:
                    print(f"  [recaptcha] ✓ solved!")
                    return True
            except Exception:
                pass

            # Fallback: check if checkbox is visually checked (green checkmark)
            try:
                checked = await page.evaluate("""() => {
                    const iframe = document.querySelector('iframe[src*="google.com/recaptcha"]');
                    if (!iframe) return false;
                    // Can't access iframe content cross-origin, but check if aria state changed
                    const container = iframe.closest('.g-recaptcha, [data-sitekey]');
                    if (container) {
                        const response = container.querySelector('.recaptcha-checkbox-checked, [aria-checked="true"]');
                        if (response) return true;
                    }
                    return false;
                }""")
                if checked:
                    print(f"  [recaptcha] ✓ checkbox checked!")
                    return True
            except Exception:
                pass

        except Exception as e:
            print(f"  [recaptcha] click error: {e}")

        await asyncio.sleep(random.uniform(1.0, 2.0))

    print(f"  [recaptcha] ✗ failed after 3 attempts")
    return False


# ── Tab management ────────────────────────────────────────────────────────────
async def _working_tab(browser: Browser) -> Page:
    """tab[0] = AdsPower health page — never touch it. Work in tab[1]."""
    ctx = browser.contexts[0]
    pages = ctx.pages
    for p in pages[2:]:          # close any extras beyond index 1
        await p.close()
        await asyncio.sleep(0.2)
    pages = ctx.pages
    if len(pages) > 1:
        return pages[1]
    return await ctx.new_page()  # open tab[1] if missing


# ── Human warmup ──────────────────────────────────────────────────────────────
async def _human_warmup(page: Page, job_url: str):
    """
    Simulates a human session before hitting Apply:
    - Lands on indeed.com (2-4s)
    - Quick scroll (trusted WheelEvents)
    - Navigates to job URL (3-6s dwell)
    Total: ~10-15s max.
    """
    from humancursor_playwright import PlaywrightCursor  # noqa: F401 — imported for cursor use in callers
    await page.goto("https://www.indeed.com", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(2.0, 4.0))
    for _ in range(random.randint(1, 2)):
        await human_scroll(page, random.randint(100, 200))
        await asyncio.sleep(random.uniform(0.3, 0.8))
    await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(random.uniform(3.0, 6.0))
    for _ in range(random.randint(1, 2)):
        await human_scroll(page, random.randint(100, 200))
        await asyncio.sleep(random.uniform(0.5, 1.5))


# ── URL type detection ────────────────────────────────────────────────────────
def _url_type(url: str) -> str:
    """Return 'viewjob', 'smartapply', or 'external'."""
    if "indeed.com/viewjob" in url or "indeed.com/rc/clk" in url:
        return "viewjob"
    if "smartapply.indeed.com" in url or "indeedapply" in url.lower():
        return "smartapply"
    return "external"


# ── Public entry point ────────────────────────────────────────────────────────
async def apply_to_job(apply_url: str, docx_path: str | None, user_id: str) -> dict:
    """
    Apply to a job. Accepts:
      - indeed.com/viewjob?...  URL  (full warmup + Apply button click)
      - smartapply.indeed.com   URL  (direct navigate into form)
      - Any external ATS URL         (direct navigate + Gemini handles form)

    docx_path  — local PDF/DOCX resume path, or None
    user_id    — AdsPower profile id
    Returns dict: {status, reason}
    """
    url_kind = _url_type(apply_url)
    is_external = url_kind == "external"
    platform = "Indeed SmartApply" if not is_external else "External ATS (Workday / Greenhouse / etc.)"

    # ── Stone-walled check ────────────────────────────────────────────────────
    db_row = _PROFILES.get(user_id, {})
    if db_row.get("stone_walled"):
        sw_at = db_row.get("stone_walled_at")
        if sw_at:
            sw_dt = datetime.fromisoformat(sw_at.replace("Z", "+00:00"))
            age_h = (datetime.now(timezone.utc) - sw_dt).total_seconds() / 3600
            if age_h < 24:
                return {"status": "skipped", "reason": f"stone_walled ({age_h:.1f}h ago — wait 24h)"}
            # Rested enough — clear the flag in DB and in local cache
            _patch_profile(user_id, {"stone_walled": False, "stone_walled_at": None})
            db_row["stone_walled"] = False
        else:
            return {"status": "skipped", "reason": "stone_walled (no timestamp — skipping)"}

    resume_path = db_row.get("resume_path") or docx_path
    profile = {
        "name":        db_row.get("full_name", ""),
        "email":       db_row.get("email", ""),
        "phone":       db_row.get("phone_number", ""),
        "years_exp":   str(db_row.get("years_exp", "3")),
        "education":   db_row.get("education", "High School Diploma"),
        "salary_hr":   str(db_row.get("salary_hr", "25")),
        "salary_yr":   str(db_row.get("salary_yr", "52000")),
        "is_external": is_external,
        "platform":    platform,
    }
    # Use DB resume_path if set, else fall back to passed-in docx_path
    if db_row.get("resume_path") and os.path.exists(db_row["resume_path"]):
        docx_path = db_row["resume_path"]
    debug_dir = f"{DEBUG_DIR_BASE}/{user_id}_{int(time.time())}"

    profile_data = _start_profile(user_id)
    debug_port   = int(profile_data["debug_port"])
    print(f"[playwright] {user_id} started → CDP port {debug_port}  [{url_kind}]")
    print(f"[playwright] screenshots → {debug_dir}/")

    page = None
    try:
        from playwright.async_api import async_playwright as vanilla_async_playwright
        async with vanilla_async_playwright() as pw:
            # ── Kill service workers before CDP connect ───────────────
            # Root cause 1: extension SWs deadlock rebrowser's addBinding patch.
            ws_url = profile_data.get("ws", {}).get("puppeteer", "")
            if ws_url:
                await _kill_service_workers(ws_url)

            # ── CDP connect via VANILLA playwright (bypass rebrowser patch) ──
            # Root cause 2: rebrowser's addBinding patch deadlocks with CF cookies
            # during browser attach. Vanilla playwright has no such patch.
            # AdsPower fingerprinting is at C++ level — not affected by this swap.
            browser = None
            for cdp_attempt in range(2):
                try:
                    browser = await pw.chromium.connect_over_cdp(
                        f"http://127.0.0.1:{debug_port}",
                        timeout=15000
                    )
                    print(f"[playwright] ✅ CDP connected via vanilla playwright (attempt {cdp_attempt+1})")
                    break
                except Exception as cdp_err:
                    if cdp_attempt == 1:
                        raise cdp_err
                    print(f"[playwright] ⚠️  CDP connect attempt 1/2 timed out — retrying...")
                    await asyncio.sleep(2)

            context = browser.contexts[0]

            # ── Build dynamic fingerprint init script from Supabase data ──
            fp = db_row.get("fingerprint") or {}
            fp_screen_w   = fp.get("screenWidth", 1440)
            fp_screen_h   = fp.get("screenHeight", 900)
            fp_avail_w    = fp.get("availWidth", fp_screen_w)
            fp_avail_h    = fp.get("availHeight", fp_screen_h - 40)
            fp_outer_w    = fp.get("outerWidth", fp_screen_w)
            fp_outer_h    = fp.get("outerHeight", fp_screen_h - 40)
            fp_dpr        = fp.get("devicePixelRatio", 1)
            fp_color_d    = fp.get("colorDepth", 24)
            fp_pixel_d    = fp.get("pixelDepth", 24)
            fp_hw_conc    = fp.get("hardwareConcurrency", 8)
            fp_dev_mem    = fp.get("deviceMemory") or 8
            fp_touch      = fp.get("maxTouchPoints", 0)
            fp_vendor     = fp.get("webglVendor", "Google Inc. (Intel)")
            fp_renderer   = fp.get("webglRenderer", "ANGLE (Intel, Mesa Intel(R) Graphics, OpenGL 4.6)")

            # Escape single quotes in GPU strings
            fp_vendor_esc   = str(fp_vendor).replace("'", "\\'")
            fp_renderer_esc = str(fp_renderer).replace("'", "\\'")

            if fp:
                print(f"[playwright] fingerprint: {fp_screen_w}x{fp_screen_h} DPR={fp_dpr} GPU={str(fp_renderer)[:50]}")
            else:
                print(f"[playwright] ⚠️  no fingerprint in DB — using fallback defaults")

            # ── Minimal stealth: main-world overrides (addBinding mode) ──────
            # AdsPower handles screen, hardware, WebGL at C++ level.
            # We only patch what AdsPower does NOT: webdriver, Battery, Permissions.
            await context.add_init_script("""(() => {
  // 1. Hide webdriver (CF checks this first — strongest bot signal)
  try {
    const proto = Object.getPrototypeOf(navigator);
    if (proto && Object.getOwnPropertyDescriptor(proto, 'webdriver')) {
      delete proto.webdriver;
    }
  } catch(e) {}
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });

  // 2. Battery API — VPS has no battery hardware, returns null.
  //    Bot detectors check this — null = headless/VPS giveaway.
  try {
    if (!navigator.getBattery) {
      navigator.getBattery = () => Promise.resolve({
        charging: true, chargingTime: 0, dischargingTime: Infinity, level: 1.0,
        addEventListener: () => {}, removeEventListener: () => {}
      });
    }
  } catch(e) {}

  // 3. Permissions API — normalize notifications query.
  //    Headless Chrome returns different values than headed.
  try {
    const origQuery = window.Permissions?.prototype?.query;
    if (origQuery) {
      window.Permissions.prototype.query = (params) => {
        if (params.name === 'notifications') {
          return Promise.resolve({ state: Notification.permission });
        }
        return origQuery.call(navigator.permissions, params);
      };
    }
  } catch(e) {}
})();""")

            # ── Runtime.enable leak: FIXED by rebrowser-patches (addBinding mode) ──

            page = await _working_tab(browser)

            # ── Route by URL type ──────────────────────────────────────────────
            if url_kind == "viewjob":
                # Full warmup flow: homepage → job page → click Apply
                await _human_warmup(page, apply_url)
                if await _is_cf(page):
                    if not await _solve_cf(page, debug_dir):
                        _cf_stonewalled(user_id)
                        return {"status": "skipped", "reason": "CF challenge — Gemini bypass failed"}

                content = await page.content()
                if "you've already applied" in content.lower() or "you already applied" in content.lower():
                    return {"status": "skipped", "reason": "Already applied"}

                await human_scroll(page)
                await _delay(2.0, 4.0)

                if await _is_cf(page):
                    if not await _solve_cf(page, debug_dir):
                        _cf_stonewalled(user_id)
                        return {"status": "skipped", "reason": "CF on job page — Gemini bypass failed"}

                apply_btn = None
                for sel in [
                    "[data-testid='indeedApplyButton']",
                    ".ia-IndeedApplyButton",
                    "button[class*='IndeedApply']",
                    "[data-indeed-apply]",
                    "#indeedApplyButton",
                ]:
                    try:
                        loc = page.locator(sel).first
                        await loc.wait_for(state="visible", timeout=3000)
                        apply_btn = loc
                        break
                    except Exception:
                        pass

                if not apply_btn:
                    for text in ["Apply with Indeed", "Apply now", "Easy Apply", "Instantly apply"]:
                        try:
                            loc = page.get_by_role("button", name=text, exact=False)
                            await loc.first.wait_for(state="visible", timeout=3000)
                            apply_btn = loc.first
                            break
                        except Exception:
                            pass

                if not apply_btn:
                    # Check for external ATS button
                    ext_btn = None
                    try:
                        ext_btn = page.get_by_text("Apply on company site", exact=False).first
                        await ext_btn.wait_for(state="visible", timeout=2000)
                    except Exception:
                        ext_btn = None

                    if ext_btn:
                        # External ATS — skip (0% success rate, burns Gemini budget)
                        print(f"[playwright] External ATS detected — skipping (not worth it)")
                        return {"status": "skipped", "reason": "External apply — company ATS (skipped)"}

                    # No apply button AND no external button — truly nothing to do
                    title = await page.title()
                    return {"status": "skipped", "reason": f"No apply button found (page: {title[:60]})"}

                try:
                    await _screenshot(page, debug_dir, "00_pre_apply_click")
                except Exception:
                    print("  ⚠️ pre-apply screenshot failed (non-fatal)")
                await apply_btn.scroll_into_view_if_needed()
                await _delay(1.5, 3.0)
                await apply_btn.click()
                await _delay(3.0, 5.0)

            elif url_kind == "smartapply":
                # SmartApply direct URL — brief indeed.com warmup first, then navigate
                print(f"[playwright] SmartApply direct — warming up indeed.com first")
                await page.goto("https://www.indeed.com", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(random.uniform(2.0, 4.0))
                for _ in range(random.randint(1, 2)):
                    await human_scroll(page, random.randint(80, 150))
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                print(f"[playwright] Navigating to SmartApply → {apply_url[:80]}")
                await page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
                await _delay(3.0, 6.0)
                if await _is_cf(page):
                    if not await _solve_cf(page, debug_dir):
                        _cf_stonewalled(user_id)
                        return {"status": "skipped", "reason": "CF on SmartApply — Gemini bypass failed"}
                await _screenshot(page, debug_dir, "00_direct_land")

            else:
                # External ATS — navigate directly
                print(f"[playwright] External ATS → {apply_url[:80]}")
                await page.goto(apply_url, wait_until="domcontentloaded", timeout=30000)
                await _delay(3.0, 6.0)
                await _screenshot(page, debug_dir, "00_direct_land")

            # ── Route to form engine ───────────────────────────────────────
            use_v2 = os.getenv("SMARTAPPLY_V2", "1") == "1"
            if use_v2:
                from src.smartapply import apply_smartapply
                return await apply_smartapply(page, docx_path, profile, debug_dir)
            else:
                return await _gemini_loop(page, docx_path, profile, debug_dir)

    except Exception as e:
        import traceback
        err_type = type(e).__name__
        err_msg  = str(e)
        print(f"[playwright] ❌ EXCEPTION: {err_type}: {err_msg}")
        traceback.print_exc()
        # Log failed session to Supabase
        try:
            requests.post(
                f"{_SB_URL}/rest/v1/apply_step_log",
                json={
                    "profile_id":  user_id,
                    "job_url":     apply_url,
                    "step":        "session_failed",
                    "action":      "exception",
                    "result":      "failed",
                    "notes":       f"{err_type}: {err_msg}",
                    "created_at":  datetime.now(timezone.utc).isoformat(),
                },
                headers={**_SB_HDRS, "Prefer": "return=minimal"},
                timeout=5,
            )
        except Exception:
            pass
        return {"status": "failed", "reason": f"{err_type}: {err_msg}"}

    finally:
        try:
            if page:
                await page.goto("https://www.indeed.com", wait_until="domcontentloaded", timeout=10000)
                await asyncio.sleep(2)
        except Exception:
            pass
        _stop_profile(user_id)
        print(f"[playwright] {user_id} stopped")


# ── Gemini agent loop ─────────────────────────────────────────────────────────
async def _gemini_loop(
    page: Page,
    docx_path: str | None,
    profile: dict,
    debug_dir: str,
) -> dict:
    return await _gemini_loop_inner(page, docx_path, profile, debug_dir)


async def _gemini_loop_inner(page: Page, docx_path: str | None, profile: dict, debug_dir: str) -> dict:
    profile = {**profile, "has_resume": bool(docx_path and os.path.exists(docx_path))}
    file_uploaded = False
    prev_url = ""
    url_stagnation = 0          # steps spent on the same URL
    consecutive_failures = 0    # consecutive action failures
    use_pro = False             # Pro takeover flag — stays True until URL changes

    for step in range(50):
        url = page.url
        print(f"\n  ── step {step:02d} ── {url[:90]}")

        # Stagnation detection — same URL for too many steps
        if url == prev_url:
            url_stagnation += 1
        else:
            url_stagnation = 0
            prev_url = url
            if use_pro:
                print("  ↩ URL changed — switching back to Flash")
                use_pro = False

        # Escalate to Pro after 2 stagnated steps
        if url_stagnation >= 2 and not use_pro:
            print(f"  ⚠️  Stagnated {url_stagnation} steps — escalating to Pro")
            await human_scroll(page, 500)
            use_pro = True
            url_stagnation = 0  # reset counter, Pro owns this page

        # Hard guards — no need to ask Gemini for these
        if "profile.indeed.com" in url:
            # Landed in the full Indeed profile/resume wizard — skip back to SmartApply
            print(f"  ⏩ profile.indeed.com detected — clicking Skip")
            for skip_sel in [
                page.get_by_role("button", name="Skip", exact=False),
                page.get_by_text("Skip", exact=True),
            ]:
                try:
                    el = skip_sel.first
                    await el.wait_for(state="visible", timeout=3000)
                    await el.click()
                    await asyncio.sleep(1)
                    break
                except Exception:
                    continue
            continue  # re-evaluate URL on next step

        if "/settings" in url and "indeed.com" in url:
            return {"status": "failed", "reason": "Redirected to account settings — complete Indeed profile first"}

        content = await page.content()
        if any(s in content for s in ["Application submitted", "application was submitted", "You applied"]):
            return {"status": "success", "reason": "Application submitted"}

        if "may not hear back from the employer" in content or "Consider additional opportunities" in content:
            return {"status": "disqualified", "reason": "Employer screening did not pass"}

        # Deterministic file upload — no Gemini needed for this step
        if not file_uploaded and docx_path and os.path.exists(docx_path):
            try:
                fi = page.locator("input[type='file']").first
                await fi.wait_for(state="attached", timeout=1000)
                await fi.set_input_files(docx_path)
                file_uploaded = True
                print(f"  📎 Uploaded: {os.path.basename(docx_path)}")
                await asyncio.sleep(1)
                continue
            except Exception:
                pass  # file input not visible yet

        # Scroll to see full context before screenshot (dropdowns, buttons)
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.3)")
            await asyncio.sleep(0.2)
        except Exception:
            pass

        # Screenshot → Gemini → action
        model = GEMINI_MODEL_PRO if use_pro else None
        if use_pro:
            print(f"  🧠 Using Pro model")
        screenshot = await _screenshot(page, debug_dir, f"step_{step:02d}")

        action = None
        for attempt in range(3):
            try:
                action = await _gemini_decide(screenshot, url, step, profile, model_override=model)
                break
            except Exception as e:
                print(f"  ⚠️  Gemini attempt {attempt + 1} failed: {e}")
                if attempt == 2:
                    return {"status": "failed", "reason": f"Gemini API error: {e}"}
                await asyncio.sleep(2)

        act = action.get("action", "")

        if act == "done":
            return {"status": "success", "reason": action.get("reason", "Gemini confirmed submission")}
        if act == "failed":
            return {"status": "failed", "reason": action.get("reason", "Gemini could not progress")}
        if act == "skip":
            return {"status": "skipped", "reason": action.get("reason", "External or incompatible apply")}

        ok = await _execute(page, action, docx_path)
        if not ok:
            consecutive_failures += 1
            print(f"  ↓ Action failed ({consecutive_failures} consecutive)")
            if consecutive_failures >= 10:
                return {"status": "failed", "reason": f"10 consecutive action failures — stuck at step {step}"}
            if consecutive_failures >= 5:
                await human_scroll(page, 250)  # scroll to find what we're missing
            # No delay — retry immediately on next loop iteration
        else:
            consecutive_failures = 0
            url_stagnation = 0
            await asyncio.sleep(0.5)  # brief wait for page to react to action

    return {"status": "failed", "reason": "Exceeded 50 steps without submission"}
