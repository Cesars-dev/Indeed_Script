# Deep Search Evaluation — Stealth Architecture
> **Status: COMPLETE** — Perplexity Deep Research results analyzed.
> Source file: `# Deep Research Prompt — Maximum Stealth Browser A.md` (workspace root)
> Research prompt: `memory/deep_research_prompt_stealth.md`
> Implementation: PENDING (do after first apply test passes)

---

## Decision: Approach B — Pure Playwright + Humanization Layer

**No nodriver in the hot path.** Stay on Playwright-over-CDP with a humanization + stealth layer.

### Why not Approach C (nodriver handoff)?
- nodriver in attach mode has **zero extra fingerprint powers** — AdsPower already handles TLS/JA3/WebGL/navigator
- Two CDP clients (even sequential) adds complexity and bug surface for zero stealth gain
- `nodriver.stop()` is safe (only closes WebSocket, doesn't call `Browser.close`) — but still unnecessary

---

## Key Findings

### CDP Events (Approach B confirmed correct)
| Question | Answer | Confidence |
|----------|--------|------------|
| `isTrusted` on CDP mouse events | ✅ YES — `Input.dispatchMouseEvent` always produces `isTrusted=true` | HIGH |
| `page.mouse.wheel()` vs `window.scrollBy()` | `scrollBy` = zero WheelEvents (detectable). `mouse.wheel()` = real trusted WheelEvent | HIGH |
| Playwright globals injected on CDP attach | ✅ YES — `__playwright__binding__`, `__pwInitScripts` injected even in attach mode | MEDIUM |
| nodriver vs playwright at CDP level | **Identical** — both just send `Input.dispatchMouseEvent` | MEDIUM-HIGH |
| `page.hover()` trajectory | Single-point teleport, not a path. Use manual `page.mouse.move()` | MEDIUM |

### Indeed's Actual Detection Model (NDSS PRISM 2026 paper — published)
Indeed runs its own in-house system **on top of** Cloudflare + HUMAN/PerimeterX:

| Feature | Our current state | Fix needed |
|---------|------------------|------------|
| `isTrusted` | ✅ CDP handles it | None |
| Honeypot triggered | ⚠️ Gemini may click wrong things | Add prompt guard |
| reCAPTCHA score | ⚠️ Fed by behavioral signals | Fix the behaviors |
| Velocity per minute | 🔴 Too fast | Add 3–12s delays between actions |
| Velocity per hour | 🔴 Unknown | Limit applies per hour per profile |
| `timeToPreview` | 🔴 We jump straight to job URL | Wait 4–10s on results, 10–30s before Apply |

### Libraries Found
| Library | What it does | Use? |
|---------|-------------|------|
| `humancursor-playwright` | Bezier curve mouse movement, random paths, `cursor.click_on(locator)` | ✅ YES |
| `playwright-stealth` | Init scripts: webdriver, plugins, WebGL, languages | ✅ YES |
| `humanization-playwright` | Built on Patchright fork — scroll inertia + typing | OPTIONAL |
| `nothingtoseehere` | Neuromotor model — nodriver-first but reusable math | OPTIONAL |

---

## Implementation Plan

**Four changes to `playwright_indeed.py`. No architecture change.**

### 1. Neutralize Playwright globals (inject init script)
After `connect_over_cdp()`, before any navigation:
```python
context = browser.contexts[0]
await context.add_init_script("""
(() => {
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined, configurable: true });
  try { delete window.__playwright__binding__; } catch(e) {}
  try { delete window.__pwInitScripts; } catch(e) {}
})();
""")
```

### 2. Replace `_scroll_down()` — use `page.mouse.wheel()` not `window.scrollBy()`
```python
async def human_scroll(page: Page, total_pixels: int = 400):
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
```

### 3. Replace warmup — Bezier cursor + timeToPreview respect
```python
async def _human_warmup(page: Page, job_url: str):
    from humancursor_playwright import PlaywrightCursor
    cursor = PlaywrightCursor(page)

    # Land on homepage, respect timeToPreview (4–10s minimum)
    await page.goto("https://www.indeed.com", wait_until="domcontentloaded")
    await asyncio.sleep(random.uniform(4.0, 9.0))

    # Scroll like reading (trusted WheelEvents)
    for _ in range(random.randint(3, 6)):
        await human_scroll(page, random.randint(150, 350))
        await asyncio.sleep(random.uniform(0.8, 2.5))

    # Navigate to job — waitanother 10–30s before Apply (timeToPreview)
    await page.goto(job_url, wait_until="domcontentloaded")
    await asyncio.sleep(random.uniform(10.0, 22.0))

    # Read the job description
    for _ in range(random.randint(3, 5)):
        await human_scroll(page, random.randint(100, 300))
        await asyncio.sleep(random.uniform(2.0, 5.0))
```

### 4. Gemini prompt — add honeypot guard
Add to `_GEMINI_PROMPT`:
```
• NEVER interact with hidden, disabled, invisible, zero-size, or off-screen elements
• NEVER fill fields labeled "do not fill", "leave blank", or similar
```

### 5. New dependencies
```
pip install humancursor-playwright playwright-stealth
```
Add to `requirements.txt`.

---

## What This Buys Us Against Indeed's 6-Feature Model

| Feature | After implementation |
|---------|---------------------|
| `isTrusted` | ✅ Already correct |
| Honeypot | ✅ Fixed by Gemini prompt guard |
| reCAPTCHA score | ✅ Improved by human timing + scroll events |
| Velocity per minute | ✅ Fixed by delays |
| Velocity per hour | ⚠️ Needs profile rotation logic in apply_runner.py |
| `timeToPreview` | ✅ Fixed by warmup timing |

---

## When to Implement

**After the first apply test passes on k19td50a.**
- First test tells us if the basic flow works (CF + SmartApply form filling)
- Human behavior layer matters most for fresh profiles — k19td50a is already warmed
- Order: run test → review screenshots → implement humanization → scale to 8 profiles
