# Memory: SmartApply Form — What We Know

## SmartApply Entry Flow

```
Job page (www.indeed.com/viewjob?jk=...)
  → Find Apply button:
      1. CSS first: [data-testid='indeedApplyButton'], .ia-IndeedApplyButton,
                   button[class*='IndeedApply'], [data-indeed-apply], #indeedApplyButton
      2. Exact text fallback: "Apply with Indeed", "Apply now", "Easy Apply"
         (best_match=False — NEVER use best_match=True)
  → Click
  → SmartApply loads at: smartapply.indeed.com/beta/indeedapply/form/...
```

**Critical**: Old bug was clicking the global nav bar ("gnav-util-viewjob") instead of the Apply widget.
Evidence: URL after click contained `from=gnav-util-viewjob`. Fixed by using CSS selectors.

## SmartApply Steps (observed so far)

| Step | URL slug | Content | Handler status |
|------|----------|---------|----------------|
| 1 | `profile-location` | Country + Zip — pre-filled | ✅ Continue button fix applied |
| 2+ | Unknown | Resume choice, employer questions, submit | → Use Gemini Vision |

**The Continue button trap**: It's often BELOW the fold. `best_match=True` matched "Save and close" (visible at top) → exited SmartApply. Fix: scroll down first → CSS `button[type='submit']` → exact text.

## Settings Redirect

If clicking Apply sends to `secure.indeed.com/settings` → account has no Indeed Resume.
**Fast fail**: detect URL contains `/settings` → return `failed: Account needs one-time profile setup`.

## Current Playwright + Gemini Architecture

```python
# playwright_indeed.py flow:
apply_to_job(apply_url, docx_path, user_id)
  ├─ _start_profile()         → AdsPower → debug_port
  ├─ connect_over_cdp()       → playwright attaches to AdsPower browser
  ├─ _working_tab()           → tab[0] untouched, use tab[1]
  ├─ goto(indeed.com)         → warmup 15–25s (bakes cf_clearance cookie)
  ├─ _human_scroll()          → simulate reading
  ├─ goto(apply_url)          → navigate to job
  ├─ find Apply button        → CSS selectors → click
  └─ _gemini_loop() — 20 steps:
        ├─ HARD GUARDS (no API call):
        │   ├─ /settings URL → fail fast
        │   ├─ success text → return success
        │   └─ disqualified text → return disqualified
        ├─ Deterministic: input[type='file'] detected → upload PDF
        ├─ page.screenshot() → Gemini Vision → JSON action
        └─ _execute(): click / fill / select_option / scroll / upload / done / failed
```

## Gemini Action Format

```json
{"action": "click",   "target": "text=Upload a resume", "reason": "select upload mode"}
{"action": "fill",    "target": "input[name='phone']",  "value": "+12068819903"}
{"action": "select",  "target": "select#education",     "value": "High School"}
{"action": "scroll",  "direction": "down"}
{"action": "done",    "reason": "Application submitted"}
{"action": "failed",  "reason": "Stuck on unknown step"}
```

## Known SmartApply Gaps (not yet handled by Gemini prompts)

- `<textarea>` free text (cover letter, "why do you want this job")
- Salary/wage inputs (different label pattern)
- Date inputs (start date)
- Checkboxes (multi-select)

**Strategy**: Run with screenshots on → review `/tmp/playwright_debug/<user_id>_<ts>/` → add to Gemini system prompt context.

## Gemini Prompt Context (what to provide)

```python
system_prompt = f"""
You are filling out a job application on Indeed SmartApply.
Applicant info:
  Name: {APPLICANT_NAME}
  Email: {email}
  Phone: {phone}
  Years experience: {APPLICANT_YEARS_EXP}
  Education: {APPLICANT_EDUCATION}
  Salary (hr): ${APPLICANT_SALARY_HR}
  Salary (yr): ${APPLICANT_SALARY_YR}

Current URL: {url}  |  Step: {step}/{max_steps}

Return ONLY JSON: {{"action": ..., "target": ..., "value": ..., "reason": ...}}
Actions: click, fill, select_option, scroll, upload, done, failed, skip
"""
```

## .env Keys Required

```
APPLICANT_NAME=           ← ⚠️ STILL BLANK — must fill before running
APPLICANT_YEARS_EXP=3
APPLICANT_EDUCATION=High School Diploma
APPLICANT_SALARY_HR=25
APPLICANT_SALARY_YR=52000
GEMINI_API_KEY=AIzaSyDI7...
GEMINI_MODEL=gemini-2.5-flash
ADSPOWER_BASE=http://127.0.0.1:50325
```
