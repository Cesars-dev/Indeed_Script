# SmartApply v2 — Surgeon Framework Step 1: AUDIT

> Read every file involved. Trace every call, data flow, dependency.
> Document what EXISTS vs what's MISSING.

---

## File Under Surgery

`src/playwright_indeed.py` — 1275 lines, single monolithic file.

---

## Function Map (call order)

```
apply_to_job(apply_url, docx_path, user_id)           L899-1144
  ├─ _PROFILES (module-level cache)                     L66
  ├─ _load_profiles()                                   L46-64
  ├─ _cf_stonewalled(user_id)                           L82-93
  ├─ _start_profile(user_id)                            L97-119
  ├─ _stop_profile(user_id)                             L122-130
  ├─ context.add_init_script(stealth JS)                L959-1028
  ├─ CDP Runtime.disable                                L1030-1038
  ├─ _working_tab(browser)                              L854-864
  │
  ├─ IF viewjob:
  │   ├─ _human_warmup(page, job_url)                   L868-885
  │   ├─ _is_cf(page)                                   L639-659
  │   ├─ _solve_cf(page, debug_dir)                     L739-850
  │   ├─ Apply button detection (hardcoded selectors)    L1063-1097
  │   └─ _screenshot                                    L161-166
  │
  ├─ IF smartapply:
  │   ├─ goto indeed.com warmup                         L1110-1114
  │   ├─ goto smartapply URL                            L1116
  │   ├─ _is_cf / _solve_cf                             L1118-1121
  │   └─ _screenshot                                    L1122
  │
  └─ _gemini_loop(page, docx_path, profile, debug_dir)  L1148
      └─ _gemini_loop_inner(...)                         L1157-1274
          ├─ Stagnation detection                        L1169-1177
          ├─ Pro escalation (2 stagnated steps)           L1179-1184
          ├─ Hard guards:
          │   ├─ profile.indeed.com → Skip               L1187-1202
          │   ├─ /settings → fail                        L1204-1205
          │   ├─ Success detection (content check)       L1207-1209
          │   └─ Disqualification detection              L1211-1212
          ├─ Deterministic file upload                   L1214-1225
          ├─ Scroll before screenshot                    L1227-1232
          ├─ _screenshot(page, debug_dir, label)         L1238
          ├─ _gemini_decide(screenshot, url, step, ...)  L270-340
          │   └─ Gemini API call (Flash or Pro)
          ├─ _execute(page, action, docx_path)           L344-635
          │   ├─ scroll → human_scroll                   L350-352
          │   ├─ upload → set_input_files                L354-360
          │   ├─ click → 11 strategies + radio fallback  L362-449
          │   ├─ fill → label/placeholder + type + auto  L451-482
          │   ├─ select_option → JS fuzzy + native + custom L484-612
          │   └─ check → label/role/locator              L614-635
          └─ Failure tracking (10 max)                   L1260-1272
```

---

## What EXISTS (keep as-is)

| Component | Lines | Status | Notes |
|-----------|-------|--------|-------|
| `apply_to_job()` | L899-1144 | ✅ Keep | Entry point — URL routing, warmup, stealth |
| Stealth init script | L959-1028 | ✅ Keep | Working CF bypass |
| `_solve_cf()` | L739-850 | ✅ Keep | Gemini-powered Turnstile solver |
| `_bypass_cf()` | L662-736 | ✅ Keep | Iframe fallback |
| `_is_cf()` | L639-659 | ✅ Keep | CF detection |
| `_human_warmup()` | L868-885 | ✅ Keep | ViewJob warmup |
| `_screenshot()` | L161-166 | ✅ Keep | JPEG 50% |
| `_execute()` | L344-635 | ✅ Keep | All action handlers (click, fill, select, check) |
| `human_scroll()` | L146-157 | ✅ Keep | CDP wheel events |
| `_human_type()` | L138-143 | ✅ Keep | Per-char typing |
| `_start/_stop_profile` | L97-130 | ✅ Keep | AdsPower lifecycle |
| `_PROFILES` cache | L44-66 | ✅ Keep | Supabase profile data |
| `_patch_profile()` | L69-79 | ✅ Keep | DB updates |

---

## What NEEDS REFACTORING

| Component | Lines | Issue | Replace With |
|-----------|-------|-------|-------------|
| `_gemini_loop_inner()` | L1157-1274 | Monolithic 120-line loop, Gemini every step, 50 retries, no DOM scanning | **Router + handlers + 6-shot budget** |
| `_GEMINI_PROMPT` | L170-268 | Generic 100-line prompt, sent every step even when unnecessary | **Targeted per-scenario prompts** (shorter, faster) |
| `_gemini_decide()` | L270-340 | Always sends screenshot, always uses generic prompt | **Only called for unknowns** |
| Stagnation detection | L1169-1184 | URL-based only, no DOM awareness | **DOM-based scenario detection** |
| Failure handling | L1260-1272 | 10 retries, no logging, no pattern learning | **6-shot budget + Supabase logging** |

---

## Dependencies (external)

| Dependency | Used By | Notes |
|-----------|---------|-------|
| `playwright.async_api` | Everything | Browser control |
| `google.genai` | `_solve_cf`, `_gemini_decide` | Gemini API |
| `requests` | `_load_profiles`, `_patch_profile`, `_start/_stop_profile` | Supabase + AdsPower |
| `dotenv` | Module load | .env config |
| `humancursor_playwright` | `_human_warmup` | Import only (not actually used for cursor) |

---

## Data Flow

```
Supabase (adspower_profiles)
    │
    ▼
_PROFILES cache (in-memory dict, loaded once at import)
    │
    ▼
apply_to_job(url, docx, user_id)
    │
    ├─ profile data → passed to _gemini_loop as `profile` dict
    │   Keys: name, email, phone, years_exp, education, salary_hr, salary_yr
    │
    ├─ AdsPower API → start browser → CDP port
    │
    ├─ Playwright → connect_over_cdp → stealth patching → page
    │
    └─ _gemini_loop(page, docx, profile, debug_dir)
        │
        ├─ Screenshot bytes → Gemini API → action JSON
        │
        └─ _execute(page, action) → Playwright actions
```

---

## What's MISSING (from brainstorm)

| Missing | Needed For | Priority |
|---------|-----------|----------|
| `_scan_dom(page)` function | DOM-first pattern detection | P0 |
| `_detect_scenario(dom, url)` function | Route to correct handler | P0 |
| Per-scenario handlers (10 types) | Deterministic form filling | P0 |
| Pattern registry (Supabase table) | Dynamic pattern loading | P1 |
| `apply_runs` table + logging | Batch reporting | P1 |
| `apply_step_log` table + logging | Failure analysis | P1 |
| `apply_patterns` table | Self-healing registry | P1 |
| Fire-and-forget async logger | Non-blocking Supabase writes | P1 |
| `pattern_audit.py` script | Post-batch pattern discovery | P2 |
| `batch_report.py` script | Post-batch summary | P2 |
| Targeted Gemini prompts | Faster, cheaper Gemini calls | P1 |
| 6-shot retry budget | Replace 50-step loop | P0 |

---

## Risks & Gotchas Found During Audit

1. **`_gemini_loop_inner` is the ONLY caller of `_execute()`** — safe to refactor the loop without touching `_execute()`
2. **`_execute()` is 290 lines** — it's the action engine and should stay untouched. Router just calls it.
3. **`_gemini_decide()` builds prompt from `_GEMINI_PROMPT` template** — the new router needs its own lighter prompts
4. **`apply_to_job()` has 3 URL paths (viewjob/smartapply/external)** — all 3 converge to `_gemini_loop()`. The refactor replaces `_gemini_loop` only.
5. **Module-level `_PROFILES` cache** — loaded once at import. New pattern registry should follow the same pattern.
6. **`humancursor_playwright` import in `_human_warmup`** — imported but never actually used for cursor movement. Dead import.
7. **`_delay()` still used in warmup/apply-button flow** — those are pre-form, not part of the loop being refactored.
8. **`_GEMINI_PROMPT` is 100 lines** — will be replaced by targeted prompts, but must keep as fallback for unknown scenarios.
