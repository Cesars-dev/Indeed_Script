# Action Plan: Full-Page + 12-Shot

## Change 1 — playwright_indeed.py L188-193: add full_page param to _screenshot
```python
# FROM:
async def _screenshot(page: Page, debug_dir: str, label: str) -> bytes:
    ...
    data = await page.screenshot(path=path, full_page=False, type="jpeg", quality=50)

# TO:
async def _screenshot(page: Page, debug_dir: str, label: str, full_page: bool = False) -> bytes:
    ...
    data = await page.screenshot(path=path, full_page=full_page, type="jpeg", quality=50)
```

## Change 2 — router.py L108-111: deterministic 2→4 shots
```python
# FROM:
        # SHOTS 1-2: Deterministic handlers
        if shot < 2:
            if shot == 1:
# TO:
        # SHOTS 1-4: Deterministic handlers
        if shot < 4:
            if shot >= 1:
```

## Change 3 — router.py L144: print message
```python
# FROM:
                print(f"  ↓ Deterministic miss (shot {shot}/6)")
# TO:
                print(f"  ↓ Deterministic miss (shot {shot}/12)")
```

## Change 4 — router.py L147-153: Flash 2→4 shots + keep viewport screenshot
```python
# FROM:
        # SHOTS 3-4: Gemini Flash with targeted prompt + screenshot
        if shot < 4:
            tier_label = "Flash"
            print(f"  💡 {tier_label} fallback (shot {shot + 1}/6)")
            screenshot = await _screenshot(page, debug_dir, f"step_{step:02d}")
# TO:
        # SHOTS 5-8: Gemini Flash with targeted prompt + screenshot
        if shot < 8:
            tier_label = "Flash"
            print(f"  💡 {tier_label} fallback (shot {shot + 1}/12)")
            screenshot = await _screenshot(page, debug_dir, f"step_{step:02d}")
```

## Change 5 — router.py L181-187: Pro 2→4 shots + FULL PAGE screenshot
```python
# FROM:
        # SHOTS 5-6: Gemini Pro
        if shot < 6:
            tier_label = "Pro"
            print(f"  🧠 {tier_label} fallback (shot {shot + 1}/6)")
            screenshot = await _screenshot(page, debug_dir, f"step_{step:02d}")
# TO:
        # SHOTS 9-12: Gemini Pro (FULL PAGE screenshot)
        if shot < 12:
            tier_label = "Pro"
            print(f"  🧠 {tier_label} fallback (shot {shot + 1}/12)")
            screenshot = await _screenshot(page, debug_dir, f"step_{step:02d}_full", full_page=True)
```

## Change 6 — router.py L216-241: exhausted message 6→12
```python
# FROM:
        # ALL 6 SHOTS EXHAUSTED
        ...
        "error_msg": "6 shots exhausted — likely new pattern",
        ...
        "reason": f"6 shots exhausted at step {step}",
        ...
        "reason": f"6 shots exhausted at step {step} — likely new pattern",
# TO:
        # ALL 12 SHOTS EXHAUSTED
        ...
        "error_msg": "12 shots exhausted — likely new pattern",
        ...
        "reason": f"12 shots exhausted at step {step}",
        ...
        "reason": f"12 shots exhausted at step {step} — likely new pattern",
```

## Total: 6 changes across 2 files
