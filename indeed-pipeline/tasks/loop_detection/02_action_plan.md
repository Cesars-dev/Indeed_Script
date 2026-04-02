# Action Plan: Loop Detection + Gemini Escalation

## Change 1 — router.py L55-62: Add stuck counter
```python
# ADD after "t0 = time.time()":
    same_url_actions = 0  # consecutive successful actions without URL change
```

## Change 2 — router.py L103-106: Reset on URL change
```python
# FROM:
        if url != prev_url:
            shot = 0
            prev_url = url

# TO:
        if url != prev_url:
            shot = 0
            same_url_actions = 0
            prev_url = url
```

## Change 3 — router.py L133-140: Escalate when stuck
```python
# FROM:
            if handled:
                shot = 0
                log(...)
                await asyncio.sleep(random.uniform(1.5, 3.0))
                continue

# TO:
            if handled:
                same_url_actions += 1
                if same_url_actions >= 3:
                    # Stuck on same page — force Gemini to look
                    print(f"  ⚠️ {same_url_actions} actions on same URL — escalating to Gemini")
                    shot = 4  # skip to Flash
                else:
                    shot = 0
                log(...)
                await asyncio.sleep(random.uniform(1.5, 3.0))
                continue
```

## Change 4 — handlers.py L255-267: Continue button verifies URL changed
```python
# FROM:
            await _human_delay()
            for sel in [...]:
                try:
                    ...
                    await el.click()
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    print(f"  ✓ button: '{btn['text'][:40]}'")
                    return True
                except Exception:
                    continue

# TO:
            await _human_delay()
            pre_click_url = page.url
            for sel in [...]:
                try:
                    ...
                    await el.click()
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                    # Check if page actually advanced
                    if page.url == pre_click_url:
                        print(f"  ⚠️ button: '{btn['text'][:40]}' clicked but page didn't advance")
                        return True  # still return True so router tracks it as same_url_action
                    print(f"  ✓ button: '{btn['text'][:40]}' → page advanced")
                    return True
                except Exception:
                    continue
```

## Total: 4 changes across 2 files
