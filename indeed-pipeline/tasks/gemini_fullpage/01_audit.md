# Audit: Full-Page Screenshots + 4 Shots Per Tier

## Files Involved

### 1. playwright_indeed.py — `_screenshot()` at L188-193
```python
async def _screenshot(page: Page, debug_dir: str, label: str) -> bytes:
    data = await page.screenshot(path=path, full_page=False, type="jpeg", quality=50)
```
- `full_page=False` — viewport only (1440x900)
- No `full_page` parameter exposed to callers

### 2. router.py — shot thresholds and screenshot calls
- L109-111: `SHOTS 1-2: Deterministic` → `if shot < 2`
- L144: print says "shot X/6"
- L148-150: `SHOTS 3-4: Flash` → `if shot < 4`
- L152: print says "shot X/6"
- L153: `screenshot = await _screenshot(page, ...)` — viewport only
- L182-184: `SHOTS 5-6: Pro` → `if shot < 6`
- L186: print says "shot X/6"
- L187: `screenshot = await _screenshot(page, ...)` — viewport only
- L217-224: `ALL 6 SHOTS EXHAUSTED` — hardcoded "6 shots"
- L241: reason string says "6 shots exhausted"

## Current: 6-shot (2+2+2)
## Target: 12-shot (4+4+4)

## Changes Needed

### A. `_screenshot()` — add `full_page` param
- L191: add `full_page=False` parameter, pass through

### B. Router shot thresholds — 2→4 per tier
- L111: `if shot < 2` → `if shot < 4`
- L112: `if shot == 1` → `if shot >= 1` (scroll on any retry)
- L150: `if shot < 4` → `if shot < 8`
- L184: `if shot < 6` → `if shot < 12`

### C. Router screenshot calls — full_page for Pro
- L153 (Flash): keep `full_page=False` (fast, focused)
- L187 (Pro): change to `full_page=True` (Pro sees everything)

### D. Comments + print statements — update "6" → "12"
- L109, L144, L148, L152, L182, L186, L217, L224, L241: update numbers
