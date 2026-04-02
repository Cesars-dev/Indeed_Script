"""
Gemini fallback — targeted prompts for unknown form patterns.
Only called when deterministic handlers can't solve a step.
"""
import json
import os
import re

from google import genai
from google.genai import types

FLASH_MODEL = "gemini-2.5-flash"
PRO_MODEL = "gemini-3.1-pro-preview"


def build_targeted_prompt(dom: dict, profile: dict, same_url_actions: int = 0) -> str:
    """
    Build a SHORT, targeted prompt from DOM data.
    Instead of generic 'look at this screenshot', tells Gemini exactly
    what elements are on the page and asks for a specific decision.
    """
    if same_url_actions >= 2:
        parts = [
            "You are filling a job application form. "
            "WARNING: You have already completed actions on this page but it has NOT advanced to a new URL. "
            "Fields you already filled are visible with values. "
            "DO NOT re-fill already-filled fields. Instead:\n"
            "1. Look for a 'Continue' or 'Next' button and CLICK it\n"
            "2. If no button visible, use 'scroll' action to reveal content below\n"
            "3. Look for any UNFILLED required fields you may have missed\n"
        ]
    else:
        parts = [
            "You are filling a job application form. "
            "The DOM state shows unanswered elements below. "
            "Pick the SINGLE NEXT ACTION to progress.\n"
        ]

    # Unanswered radios
    for rg in dom.get("radios", []):
        if not any(o["selected"] for o in rg["options"]):
            opts = ", ".join(o["text"] for o in rg["options"] if o["text"])
            parts.append(f"RADIO: \"{rg['question']}\" → [{opts}]")

    # Empty required inputs
    for inp in dom.get("inputs", []):
        if not inp["value"]:
            req = " (REQUIRED)" if inp["required"] else ""
            parts.append(f"INPUT: \"{inp['label']}\"{req} (type={inp['type']})")

    # Empty selects
    for sel in dom.get("selects", []):
        if not sel["value"]:
            opts = ", ".join(o["text"] for o in sel["options"][:6] if o["text"])
            parts.append(f"DROPDOWN: \"{sel['label']}\" → [{opts}]")

    # Unchecked checkboxes
    for cb in dom.get("checkboxes", []):
        if not cb["checked"]:
            parts.append(f"CHECKBOX: \"{cb['label']}\" (unchecked)")

    # File inputs
    if dom.get("file_inputs", 0) > 0:
        parts.append(f"FILE_INPUT: {dom['file_inputs']} file upload input(s) — use 'upload' action, do NOT click any button")

    # Errors
    for err in dom.get("errors", []):
        parts.append(f"ERROR: {err}")

    # Buttons
    btns = [b["text"] for b in dom.get("buttons", []) if not b["disabled"]][:5]
    if btns:
        parts.append(f"BUTTONS: {btns}")

    # Profile summary (one line)
    parts.append(
        f"\nAPPLICANT: {profile.get('name', 'N/A')}, "
        f"{profile.get('years_exp', '3')} yrs exp, "
        f"${profile.get('salary_hr', '25')}/hr, "
        f"${profile.get('salary_yr', '52000')}/yr, "
        f"education: {profile.get('education', 'High School')}"
    )

    # External ATS-specific guidance
    if profile.get("is_external"):
        parts.append("""
EXTERNAL ATS CONTEXT:
This is a company career site (Workday, Greenhouse, Lever, iCIMS, etc.), NOT Indeed SmartApply.
- If you see "Sign in" / "Create account" / "Log in to apply" / "Register" → return failed
- If you see CAPTCHA that needs solving → return failed
- Look for "Apply" / "Submit Application" / "Apply for this Job" / "Start Application" buttons
- Upload resume when a file input appears (use upload action, NOT click on file button)
- Fill name, email, phone when fields appear
- Do NOT try to register or create an account — we have no credentials for this site
- "Application submitted" / "Thank you for applying" → return done""")


    parts.append("""
Reply with ONLY valid JSON — no markdown, no explanation:
{
  "action": "click|fill|select_option|check|scroll|upload|done|failed",
  "target": "exact visible text of element",
  "value": "text to type or option to select (fill/select_option only)",
  "reason": "one line"
}

RULES:
- click → for buttons, radios, cards
- fill → for text/number inputs
- select_option → for dropdowns
- check → for checkboxes
- upload → for file inputs (resume/CV). NEVER click 'Select file', 'Choose file', or 'Upload' buttons — that opens an OS dialog the browser cannot control. Use the upload action instead.
- done → application is submitted
- failed → stuck, unrecoverable
- Include question context in radio targets (e.g. "speak Spanish Yes")""")

    return "\n".join(parts)


async def gemini_decide(screenshot: bytes, dom: dict, profile: dict, use_pro: bool = False, same_url_actions: int = 0) -> dict:
    """Send targeted prompt + screenshot to Gemini. Returns action dict."""
    prompt = build_targeted_prompt(dom, profile, same_url_actions=same_url_actions)
    model = PRO_MODEL if use_pro else FLASH_MODEL

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
    resp = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=screenshot, mime_type="image/jpeg"),
            prompt,
        ],
    )
    raw = resp.text.strip()
    # Clean markdown fences if Gemini wraps in ```json
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Regex fallback — extract first JSON object
        m = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        print(f"  ⚠️ Gemini returned unparseable JSON: {raw[:100]}")
        return {"action": "scroll", "target": "", "reason": "bad JSON — scrolling to retry"}
