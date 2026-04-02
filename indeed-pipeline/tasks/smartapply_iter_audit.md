# Surgeon Audit — SmartApply Questions Loop + External ATS Skip

## Scope
Fix the 44% → 60%+ SmartApply success rate by addressing the questions-page loop, 
and eliminate external ATS waste (0% success, burns time + Gemini budget).

---

## File 1: `src/smartapply/router.py` (422 lines)

### Data Flow
```
for step in range(50):
  1. DOM scan → detect success/disqualification  
  2. SHOTS 1-4: Deterministic handlers (radio, text, dropdown, checkbox, continue)
  3. SHOTS 5-8: Gemini Flash (viewport screenshot + targeted prompt)
  4. SHOTS 9-12: Gemini Pro (FULL PAGE screenshot + pro model)
  5. All 12 exhausted → return failed
```

### BUG: Flash same-URL loop (lines 267-288)
After Flash fills a field successfully but URL doesn't change:
- Line 274: `same_url_actions += 1`
- Line 276-280: Tries `handle_continue_button` → **fails (button below fold)**
- Line 283-285: If `same_url_actions >= 3` → **jumps to Pro (shot=8)**
- **NEVER scrolls down.** Continue button is invisible.
- **NEVER resets to deterministic.** Burns 3 more Flash shots instead.

### BUG: Pro same-URL loop (lines 358-374)
Same issue at Pro tier:
- Line 363: `same_url_actions += 1`
- Line 366-370: Tries `handle_continue_button` → **might fail even with full-page**
- Line 373: `shot += 1` → advances to exhaustion
- **Never passes back to deterministic** after a successful Gemini action

### FINDING: Deterministic scroll exists but only for det retry
- Line 156-162: Scrolls 30% on `shot >= 1` (deterministic retry)
- But this scroll only happens in deterministic tier, not after Gemini fills

### FINDING: `gemini_decide()` prompt has no stuck context
- `build_targeted_prompt()` at line 226 receives `dom` and `profile` only
- No `same_url_actions` parameter — Gemini has zero awareness of being stuck
- Gemini may re-answer the same question or suggest same action

---

## File 2: `src/smartapply/gemini_fallback.py` (126 lines)

### `build_targeted_prompt(dom, profile)` — line 15
- Takes only `dom` and `profile` — no stuck context
- Prompt starts with: "Pick the SINGLE NEXT ACTION to progress"
- Valid actions include `scroll` (line 89) but prompt never suggests it
- DOM reports filled fields correctly (they have `value`), but unfilled ones
  below fold are invisible to the DOM scanner → Gemini only sees what DOM sees

### `gemini_decide(screenshot, dom, profile, use_pro)` — line 108
- Signature: `(screenshot, dom, profile, use_pro)` — no `same_url_actions`
- Need to add parameter to pass stuck context through

---

## File 3: `src/playwright_indeed.py` (1603 lines)

### External ATS routing (lines 1353-1391)
- Line 1357: Detects "Apply on company site" button
- Lines 1362-1391: Clicks through, handles new tab, calls `external_ats_apply`
- **0/8 success rate** — all fail on complex enterprise ATS (Oracle, Workday)
- **Change needed:** Return skipped immediately instead of routing to handler

---

## File 4: `src/smartapply/dom_scanner.py`

### DOM visibility limitation
- Scans DOM for inputs, radios, selects, checkboxes
- Reports ALL elements on page, not just visible ones
- But: if the page uses lazy rendering, below-fold elements may not be in DOM
- This is why Gemini doesn't see unfilled fields below the fold

---

## Stonewalled Profiles
**None.** All 19 profiles have `stone_walled=False`. 
- Oswaldin (Slot 10, resting): 3 CF hits, 9 total applies — most used but clean
- All 4 active profiles: 0 CF hits, 0 applies in DB — fresh

---

## Summary of Issues

| ID | Issue | Location | Impact |
|----|-------|----------|--------|
| A1 | Flash never scrolls after fill | router.py:267-288 | 9 failures |
| A2 | Gemini prompt lacks stuck context | gemini_fallback.py:15-105 | 9 failures |
| A3 | After Gemini fill, never resets to deterministic | router.py:267-288 | Wastes Gemini shots |
| A4 | External ATS burns 200s + 8 Gemini calls for 0% | playwright_indeed.py:1362-1391 | 8 failures |
| A5 | Full-page screenshot only on Pro (shots 9-12) | router.py:219 vs 309 | Delayed context |

