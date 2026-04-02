# Surgeon Cross-Reference — Iteration 8

## Audit Issue → Plan Coverage

| Audit Issue | Addressed in Plan? | Notes |
|-------------|-------------------|-------|
| A1: Dedup skips all URLs | ✅ Change 1 | Adds status+reason filter, TRANSIENT_PATTERNS list |
| A2: json.loads crashes | ✅ Change 2 | try/except + regex fallback + safe default |
| A3: 50-step runaway | ✅ Change 3 | `same_url_actions >= 6` bail-out in Flash + Pro |
| A4: Transient burns budget | ✅ Change 4 | `is_transient` check, `continue` instead of count |
| A5: Generic resume | ✅ Change 5 | Per-job Google Doc download + cache |

## Plan Change → Audit Support

| Plan Change | Supported by Audit? | Notes |
|-------------|-------------------|-------|
| C1: Smart dedup | ✅ A1 traces lines 93-116 | SELECT needs `status,reason` added |
| C2: JSON fallback | ✅ A2 traces line 136 | Regex pattern handles nested JSON |
| C3: Bail-out | ✅ A3 traces line 275 + ~367 | Both Flash AND Pro tiers |
| C4: Transient skip | ✅ A4 traces lines 230-245 | Uses same TRANSIENT_PATTERNS as C1 |
| C5: Cover letter | ✅ A5 traces lines 73-201 | doc_url from CSV, download as PDF |

## Contradictions / Gaps

| # | Issue | Resolution |
|---|-------|------------|
| 1 | C4 uses `continue` in `while not success` loop — will this re-increment `url_attempts`? | YES — line 190: `url_attempts += 1`. Transient retries SHOULD increment url_attempts so we don't infinite-retry. After 2 transient failures on same URL, it moves on (line 233). This is correct. |
| 2 | C5 changes `_RAW_URLS` (list of strings) to `_RAW_JOBS` (list of dicts). Does dedup still work? | Must update line 116: from `u[:100] not in _ATTEMPTED` to `j["url"][:100] not in _ATTEMPTED`. Plan says this — confirmed. |
| 3 | C1 TRANSIENT_PATTERNS and C4 TRANSIENT_PATTERNS are the same list — should be defined once. | Define `TRANSIENT_PATTERNS` at module level (near line 67) and reuse in both functions. |
| 4 | C3: bail-out returns `{"status": "failed"}` — will this be logged as a real failure or transient? | The reason says "form too complex" which doesn't match any TRANSIENT_PATTERN — so it counts as a real failure. Correct behavior. |
| 5 | C5: Google Doc export URL requires the doc to be publicly accessible or use OAuth. | The CSV has `?usp=drivesdk` sharing links. Export URL `docs.google.com/document/d/{ID}/export?format=pdf` works if doc is shared with "anyone with link". Need to verify. If auth required, fall back to generic resume. Plan already handles this in try/except. |
| 6 | C2: regex `r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'` — does this handle nested JSON? | Handles one level of nesting (action dict has no nested objects). Sufficient for our `{"action": ..., "target": ..., "value": ..., "reason": ...}` format. |

## Open Items: NONE
All gaps resolved. Ready for preflight.
