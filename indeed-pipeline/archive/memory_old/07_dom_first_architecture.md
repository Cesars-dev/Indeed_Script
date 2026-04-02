# SmartApply v2 — Brainstorm

> Router + specialized handlers + self-healing pipeline

---

## Core Idea

Replace the monolithic Gemini-per-step loop with:
1. **DOM scan** (free, <100ms) to identify the pattern
2. **Route** to the right sub-handler
3. **Deterministic handler** (3-5s human delay) does the action
4. **Gemini Flash** only when no pattern matches — with a targeted prompt
5. **Self-healing** — failures create new patterns automatically

---

## Architecture

```
smartapply_router.py (main)
  │
  ├─ _scan_dom(page) → structured form data (<100ms)
  ├─ _detect_scenario(dom_data) → scenario ID
  │
  ├─ Scenario 1:  contact_info     → fill phone, click Continue
  ├─ Scenario 2:  location         → click Continue (pre-filled)
  ├─ Scenario 3:  resume_upload    → upload file, click Continue
  ├─ Scenario 4:  privacy          → click Continue (pre-selected)
  ├─ Scenario 5:  radio_yesno      → match question → Yes/No
  ├─ Scenario 6:  radio_range      → "2-5 years", "Less than 20%"
  ├─ Scenario 7:  text_input       → phone/wage/years from profile
  ├─ Scenario 8:  dropdown_select  → read options, fuzzy pick
  ├─ Scenario 9:  checkbox         → check all
  ├─ Scenario 10: review_submit    → click Submit/Review
  │
  └─ Scenario ??: UNKNOWN → Gemini Flash with PRE-CHEWED prompt:
       "Page has a radio group: 'Do you have a CDL license?'
        Options: Yes, No
        Profile: medical receptionist, no CDL
        → pick one"
```

---

## Per-Step Flow

```python
async def _smart_step(page, profile):
    # 1. DOM scan (free, instant)
    dom = await _scan_dom(page)  # returns {radios, inputs, selects, buttons, ...}
    
    # 2. Check success/failure signals
    if dom["success"]: return {"status": "success"}
    if dom["error"]:   return {"status": "failed"}
    
    # 3. Detect scenario
    scenario = _detect_scenario(dom, page.url)
    
    # 4. Route to handler
    if scenario != "unknown":
        await asyncio.sleep(random.uniform(3, 5))  # human delay
        ok = await HANDLERS[scenario](page, dom, profile)
        if ok: return {"status": "continue"}
    
    # 5. Gemini Flash with targeted prompt (only for unknowns)
    prompt = _build_targeted_prompt(dom, profile)  # NOT generic — specific to what failed
    screenshot = await _screenshot(page, ...)
    action = await _gemini_decide(screenshot, prompt)
    return await _execute(page, action)
```

---

## Self-Healing Pipeline

When a step **fails** (handler returns False, or 3+ retries):

### Phase 1: Log the failure
```python
# Store to Supabase: failed_patterns table
{
    "job_id": "...",
    "url": page.url,
    "dom_snapshot": dom,          # full DOM structure
    "screenshot_path": "...",     # screenshot for visual reference
    "attempted_action": action,   # what we tried
    "error": "element not found", # why it failed
    "timestamp": now
}
```

### Phase 2: Audit script (offline, async)
Runs after failures accumulate (cron or manual trigger):
```
audit_failed_patterns.py
  1. Read failed_patterns from Supabase
  2. Group by DOM similarity (same form structure = same pattern)
  3. For each new pattern cluster:
     a. Analyze DOM → identify element types
     b. Generate deterministic handler code
     c. Save as new scenario handler
     d. Update pattern registry
     e. Wire to router
```

### Phase 3: Self-wire
```python
# pattern_registry.json (or Supabase table)
{
    "patterns": [
        {
            "id": "cdl_license_radio",
            "dom_signal": {"radio_question_contains": "CDL"},
            "handler": "radio_yesno",
            "default_answer": "No",
            "created_from": "failed_pattern_id_123"
        }
    ]
}
```

The router reads this registry at startup. New patterns auto-discovered
from failures get added without code changes.

---

## Targeted Gemini Prompts (when called)

Instead of sending a generic "figure out this page" prompt,
send Gemini EXACTLY what it needs to decide:

### Before (current — generic):
```
"You are controlling a browser to submit a job application.
 Look at the screenshot. Choose the SINGLE NEXT ACTION..."
 [60KB screenshot]
```
→ Gemini has to: find elements + read text + understand context + decide

### After (targeted — pre-chewed):
```
"Question: 'Do you have a valid driver's license?'
 Options: Yes, No
 Applicant: medical receptionist, no driving required
 → Reply with just the answer text to select"
```
→ Gemini just picks the answer. 1 sentence response. Way faster.

Screenshot only sent if DOM scan couldn't extract the text
(e.g., custom styled components).

---

## DOM Scanning — What We Extract

```javascript
// page.evaluate() — runs in browser, returns structured data
{
  url: window.location.href,
  
  // Buttons
  buttons: [...document.querySelectorAll('button, [role="button"]')]
    .map(b => ({text: b.textContent.trim(), type: b.type, disabled: b.disabled})),
  
  // Radio groups
  radios: [...document.querySelectorAll('fieldset, [role="radiogroup"]')]
    .map(fg => ({
      question: fg.querySelector('legend, label')?.textContent.trim(),
      options: [...fg.querySelectorAll('input[type="radio"]')]
        .map(r => ({
          text: (r.labels?.[0] || r.nextElementSibling)?.textContent.trim(),
          selected: r.checked
        }))
    })),
  
  // Text inputs
  inputs: [...document.querySelectorAll('input[type="text"], input[type="number"], input[type="tel"], textarea')]
    .filter(i => i.offsetParent !== null)  // visible only
    .map(i => ({
      label: document.querySelector(`label[for="${i.id}"]`)?.textContent.trim() || i.placeholder,
      value: i.value,
      required: i.required,
      type: i.type
    })),
  
  // Selects
  selects: [...document.querySelectorAll('select')]
    .map(s => ({
      label: document.querySelector(`label[for="${s.id}"]`)?.textContent.trim(),
      value: s.value,
      options: [...s.options].map(o => ({text: o.text, value: o.value, selected: o.selected}))
    })),
  
  // Checkboxes
  checkboxes: [...document.querySelectorAll('input[type="checkbox"]')]
    .filter(c => c.offsetParent !== null)
    .map(c => ({
      label: (c.labels?.[0])?.textContent.trim(),
      checked: c.checked
    })),
  
  // File inputs
  fileInputs: document.querySelectorAll('input[type="file"]').length,
  
  // Success/error signals
  success: document.body.textContent.includes('Application submitted') ||
           document.body.textContent.includes('You applied'),
  errors: [...document.querySelectorAll('[class*="error"], [role="alert"]')]
    .map(e => e.textContent.trim())
}
```

---

## Timing Budget

| Step Type | Delay | Source |
|-----------|-------|--------|
| DOM scan | <100ms | page.evaluate() — free |
| Pattern detection | <1ms | Python dict lookup |
| Deterministic action | 3-5s | `asyncio.sleep(random.uniform(3, 5))` |
| Gemini Flash (unknown) | 8-12s | API latency (natural delay) |
| Gemini Pro (escalation) | 15-20s | API latency (natural delay) |

**Target:** 10-15 steps × 3-5s = **30-75s per app** (deterministic)
**With Gemini steps:** add 10-15s per unknown = **2-3 min worst case**

---

## Retry Budget (5 Shots Per Page)

**Never retry endlessly. 6 shots max, then log and move on.**

```
Shot 1: Deterministic handler (3-5s)
Shot 2: Deterministic + scroll (3-5s)    ← catches timing/visibility misses
Shot 3: Flash + targeted prompt (8-12s)
Shot 4: Flash retry (8-12s)
Shot 5: Pro (15-20s)
Shot 6: Pro retry (15-20s)
FAIL  → log DOM + screenshot → move to next job
```

- **Why 2 deterministic?** First miss could be timing (element not rendered).
  Second try with scroll catches that. If both miss = new pattern.
- **Why 2 Flash?** First might pick wrong element. Second sees the error.
- **Why 2 Pro?** Pro deserves a fair shot — first attempt reads context,
  second can course-correct. If Pro fails twice, it's genuinely new.
- **Total worst case per stuck page: ~60s**
- **At 100 jobs: ~90% patterns matched** — failures feed self-healing loop

Every new page (URL change) → reset to Shot 1.

---

## Async Logger (Fire-and-Forget)

**Logging must NEVER block the pipeline.** Fire the log, keep working.

```python
# Option A: subprocess (truly fire-and-forget, 10ms overhead)
import subprocess, json

def log_step(table, data):
    subprocess.Popen(
        ["python3", "src/smartapply/async_logger.py", table, json.dumps(data)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

# Option B: asyncio task (no subprocess, same thread, non-blocking)
async def log_step_async(table, data):
    asyncio.create_task(_post_to_supabase(table, data))
    # returns immediately, POST happens in background

# async_logger.py (standalone script for Option A)
# Receives table + JSON from stdin/argv, POSTs to Supabase, exits
import sys, requests, os, json
from dotenv import load_dotenv
load_dotenv()

table = sys.argv[1]
data = json.loads(sys.argv[2])
requests.post(
    f"{os.getenv('SUPABASE_URL')}/rest/v1/{table}",
    json=data,
    headers={
        "apikey": os.getenv("SUPABASE_KEY"),
        "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}",
        "Content-Type": "application/json"
    },
    timeout=5
)
```

**Option B is cleaner** — no subprocess, just an async task that runs in the
event loop background. Pipeline never waits for it.

---

## Files Structure

```
src/
  smartapply/
    router.py            ← main loop, scenario detection
    dom_scanner.py       ← _scan_dom() JS + Python parser
    pattern_registry.py  ← known patterns + answer mappings
    handlers/
      contact_info.py
      location.py
      resume_upload.py
      privacy.py
      radio_yesno.py
      radio_range.py
      text_input.py
      dropdown.py
      checkbox.py
      review_submit.py
    gemini_fallback.py   ← targeted prompt builder + API call
    self_heal.py         ← failure logger + pattern auditor
```

---

## Open Questions

1. Should pattern_registry be in Supabase or local JSON?
   → Supabase = shared across VPS instances, but adds latency
   → Local JSON = fast, but needs deploy to update
   → **Hybrid:** load from Supabase at startup, cache locally

2. Do we keep the current `_gemini_loop` as fallback?
   → Yes — if router crashes, fall back to current behavior
   → Wrap in try/except, log to Supabase

---

## Supabase Logging Schema

### Table: `apply_runs` — one row per job application attempt

```sql
CREATE TABLE apply_runs (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    job_id        TEXT NOT NULL,                    -- Indeed job key (jk=...)
    profile_id    TEXT NOT NULL,                    -- AdsPower user_id
    profile_name  TEXT,                             -- human name (e.g., "Gabriela")
    job_url       TEXT NOT NULL,
    job_title     TEXT,
    company       TEXT,
    
    -- Result
    status        TEXT NOT NULL,                    -- success | failed | skipped | disqualified | stonewalled
    reason        TEXT,                             -- "Application submitted" / "10 consecutive failures at step 14"
    
    -- Timing
    started_at    TIMESTAMPTZ DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    elapsed_s     FLOAT,                           -- total seconds
    
    -- Stats
    total_steps       INT,                         -- how many steps taken
    deterministic_steps INT DEFAULT 0,             -- steps handled without Gemini
    flash_steps       INT DEFAULT 0,               -- steps handled by Flash
    pro_steps         INT DEFAULT 0,               -- steps handled by Pro
    failed_steps      INT DEFAULT 0,               -- steps that returned False
    
    -- Debugging
    debug_dir         TEXT,                        -- path to screenshots folder
    last_screenshot   TEXT,                        -- path to final screenshot
    last_url          TEXT,                        -- URL when finished
    
    -- Batch context
    batch_id          TEXT,                        -- groups runs in same batch
    
    CONSTRAINT fk_profile FOREIGN KEY (profile_id) 
      REFERENCES adspower_profiles(user_id)
);
```

### Table: `apply_step_log` — one row per step (granular)

```sql
CREATE TABLE apply_step_log (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    run_id        UUID REFERENCES apply_runs(id) ON DELETE CASCADE,
    step_num      INT NOT NULL,
    
    -- Page context
    url           TEXT,
    page_pattern  TEXT,                            -- "contact_info" / "radio_yesno" / "unknown"
    
    -- Decision
    tier          TEXT NOT NULL,                   -- "deterministic" / "flash" / "pro"
    action        JSONB,                           -- {"action": "click", "target": "Yes", ...}
    
    -- Result
    success       BOOLEAN NOT NULL,
    error_msg     TEXT,                            -- "element not found — 'speak Spanish Yes'"
    
    -- DOM snapshot (for failed steps only, to avoid bloat)
    dom_snapshot   JSONB,                          -- full DOM scan result (only on failure)
    screenshot_path TEXT,                          -- only stored on failure
    
    -- Timing
    duration_ms    INT,                            -- how long this step took
    created_at     TIMESTAMPTZ DEFAULT now()
);

-- Index for querying failures
CREATE INDEX idx_step_log_failures ON apply_step_log(success) WHERE success = FALSE;
CREATE INDEX idx_step_log_run ON apply_step_log(run_id);
```

### Table: `apply_patterns` — learned patterns registry

```sql
CREATE TABLE apply_patterns (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    pattern_id      TEXT UNIQUE NOT NULL,           -- "cdl_license_radio", "spanish_yesno"
    
    -- Detection
    dom_signal      JSONB NOT NULL,                 -- {"element": "radio", "question_contains": "CDL"}
    
    -- Action
    handler         TEXT NOT NULL,                  -- "radio_yesno" / "text_input" / "dropdown"
    default_answer  TEXT,                           -- "No" / "Yes" / "3"
    
    -- Provenance
    source          TEXT DEFAULT 'manual',          -- "manual" / "self_heal" / "gemini_discovered"
    discovered_from UUID,                           -- FK to apply_step_log that first failed
    
    -- Stats
    times_used      INT DEFAULT 0,
    times_succeeded INT DEFAULT 0,
    success_rate    FLOAT GENERATED ALWAYS AS 
      (CASE WHEN times_used > 0 THEN times_succeeded::float / times_used ELSE 0 END) STORED,
    
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

---

## Batch Reporting

After every batch run, generate a report:

```python
# batch_report.py — runs after batch completes

async def generate_batch_report(batch_id):
    """Query Supabase, generate markdown report."""
    
    runs = supabase.table("apply_runs").select("*").eq("batch_id", batch_id).execute()
    
    report = {
        "batch_id": batch_id,
        "total_jobs": len(runs),
        "successful": [r for r in runs if r["status"] == "success"],
        "failed":     [r for r in runs if r["status"] == "failed"],
        "skipped":    [r for r in runs if r["status"] == "skipped"],
        "disqualified": [r for r in runs if r["status"] == "disqualified"],
        "stonewalled":  [r for r in runs if r["status"] == "stonewalled"],
        
        # Timing
        "avg_time_s": avg([r["elapsed_s"] for r in runs]),
        "total_time_s": sum([r["elapsed_s"] for r in runs]),
        
        # Gemini usage
        "total_deterministic_steps": sum(r["deterministic_steps"] for r in runs),
        "total_flash_steps": sum(r["flash_steps"] for r in runs),
        "total_pro_steps": sum(r["pro_steps"] for r in runs),
        
        # Failures breakdown
        "failure_reasons": group_by([r["reason"] for r in runs if r["status"] == "failed"]),
    }
    
    # For each failed job: attach last screenshot + step log
    for fail in report["failed"]:
        fail["step_log"] = supabase.table("apply_step_log") \
            .select("*").eq("run_id", fail["id"]).eq("success", False).execute()
    
    return report
```

### Report output (per batch):

```
╔══════════════════════════════════════╗
║     BATCH REPORT — 2026-03-13       ║
╠══════════════════════════════════════╣
║  ✅ Successful:    14/20 (70%)       ║
║  ❌ Failed:         4/20 (20%)       ║
║  ⏭️  Skipped:       1/20 (5%)        ║
║  🚫 Disqualified:  1/20 (5%)        ║
╠══════════════════════════════════════╣
║  ⏱️  Avg time:      2m 15s           ║
║  🤖 Deterministic: 85% of steps     ║
║  💡 Flash calls:   12 total          ║
║  🧠 Pro calls:     3 total           ║
╠══════════════════════════════════════╣
║  FAILURES:                           ║
║  • 2x "element not found" (radio)    ║
║  • 1x "screenshot timeout" (CF)      ║
║  • 1x "10 consecutive failures"      ║
║                                       ║
║  NEW PATTERNS DETECTED: 2            ║
║  → "CDL license" radio (→ No)        ║
║  → "shift preference" dropdown       ║
╚══════════════════════════════════════╝
```

---

## Self-Healing Loop (Gemini-Powered Pattern Discovery)

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│ Batch runs   │────▶│ apply_runs   │────▶│ Batch Report  │
│ (20 jobs)    │     │ apply_steps  │     │ (success/fail)│
└─────────────┘     └──────┬───────┘     └───────┬───────┘
                           │                      │
                    failed steps              new patterns?
                           │                      │
                    ┌──────▼───────┐     ┌────────▼────────┐
                    │ DOM snapshots │────▶│ pattern_audit.py│
                    │ screenshots   │     │ (Gemini Flash)  │
                    └──────────────┘     └────────┬────────┘
                                                  │
                                         ┌────────▼────────┐
                                         │ Generate new     │
                                         │ handler .py file │
                                         │ + registry entry │
                                         └────────┬────────┘
                                                  │
                                         ┌────────▼────────┐
                                         │ Wire to router   │
                                         │ (import + add    │
                                         │  to HANDLERS)    │
                                         └─────────────────┘
```

### pattern_audit.py — How it works:

```python
async def audit_failures(batch_id):
    """Analyze failed steps, discover new patterns, generate handlers."""
    
    # 1. Get all failed steps from this batch
    failures = supabase.table("apply_step_log") \
        .select("*, apply_runs!inner(batch_id)") \
        .eq("success", False) \
        .eq("apply_runs.batch_id", batch_id) \
        .execute()
    
    # 2. Group by DOM similarity
    clusters = cluster_by_dom(failures)  # group by similar form structure
    
    for cluster in clusters:
        # 3. Check if pattern already exists
        existing = supabase.table("apply_patterns") \
            .select("*").ilike("dom_signal", f"%{cluster.key_element}%").execute()
        if existing.data:
            continue  # already known
        
        # 4. Ask Gemini Flash to analyze the DOM + suggest a handler
        prompt = f"""
        These {len(cluster.failures)} job applications failed on the same form element.
        
        DOM element: {cluster.dom_element}
        Question text: {cluster.question_text}
        Options: {cluster.options}
        Error: {cluster.error}
        
        1. What is the correct answer for a medical receptionist?
        2. What pattern detection rule should I use? (keyword in question)
        3. What handler type? (radio_yesno / text_input / dropdown / custom)
        
        Reply as JSON:
        {{"answer": "...", "keyword": "...", "handler": "...", "confidence": 0.0-1.0}}
        """
        
        result = await gemini_flash(prompt)  # no screenshot needed, just DOM text
        
        if result["confidence"] >= 0.8:
            # 5. Auto-create pattern entry
            supabase.table("apply_patterns").insert({
                "pattern_id": f"{result['keyword'].replace(' ', '_')}_{result['handler']}",
                "dom_signal": {"element": result["handler"].split("_")[0], 
                               "question_contains": result["keyword"]},
                "handler": result["handler"],
                "default_answer": result["answer"],
                "source": "gemini_discovered",
                "discovered_from": cluster.failures[0]["id"]
            }).execute()
            
            print(f"  🧬 New pattern: {result['keyword']} → {result['answer']}")
        else:
            # Low confidence — flag for manual review
            print(f"  ⚠️  Low confidence pattern, needs manual review: {cluster.question_text}")
```

### Key principle: NEVER mess with router.py

New patterns are data, not code. The router reads `apply_patterns` 
from Supabase at startup and dynamically routes. Adding a pattern = 
inserting a row, not editing Python.

```python
# In router.py — dynamic pattern loading
class SmartApplyRouter:
    def __init__(self):
        # Load patterns from Supabase once at startup
        self.patterns = load_patterns_from_supabase()
    
    def _detect_scenario(self, dom):
        # Check dynamic patterns first (newest, most specific)
        for pattern in self.patterns:
            if self._matches(dom, pattern["dom_signal"]):
                return pattern
        
        # Then check hardcoded page handlers
        if "/contact-info" in dom["url"]:
            return {"handler": "contact_info"}
        # ...
```

