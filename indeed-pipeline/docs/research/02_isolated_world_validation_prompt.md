# Perplexity Research #2 — Do init script overrides reach the main world?

> Prompt sent: 2026-03-14 ~00:48 CST
> Source: rag_validation_prompt.md

## Prompt Summary
Asked whether Battery API, Permissions API, and navigator.webdriver overrides in our init script actually reach the main world (where CF operates) given `alwaysIsolated` mode. 7 targeted questions about isolated vs main world behavior, CF re-challenge patterns, and alternative injection methods.

## Critical Findings

### None of our overrides reach the main world
- Under `alwaysIsolated`, ALL `context.add_init_script()` code runs in isolated world
- `navigator.getBattery` shim → **invisible to CF** (different navigator object)
- `Permissions.prototype.query` override → **invisible to CF** (different prototype)
- `navigator.webdriver = undefined` → **invisible to CF** (only hides from Playwright's own checks)
- **CF still sees `navigator.webdriver === true`** — one of the strongest bot signals

### Recommended: Switch to `addBinding` mode
- `addBinding` is rebrowser's default mode and "ultimate approach"
- Init scripts run in **main world** — overrides become visible to CF
- No known cons per rebrowser docs
- Still hides `Runtime.enable` CDP leak

### Alternative: Raw CDP injection
```python
cdp = await context.new_cdp_session(page)
await cdp.send("Page.addScriptToEvaluateOnNewDocument", {
    "source": "/* JS */",
    "worldName": ""  # empty = main world
})
```
- Works even with `alwaysIsolated`
- Injects directly into main world
- Compatible with rebrowser-patches

### CF Turnstile re-challenge behavior
- Solving once produces a token/cookie that **helps** but doesn't guarantee no re-challenge
- Datacenter IP + automation signals = high risk score = likely re-challenge
- CF does NOT explicitly detect CDP WebSocket connections
- CF cares about `Runtime.enable` leaks (which rebrowser already fixes)
- Keeping `navigator.webdriver === true` visible keeps risk score HIGH

## Action Plan
1. Switch to `REBROWSER_PATCHES_RUNTIME_FIX_MODE=addBinding`
2. Keep init script minimal: webdriver + Battery + Permissions ONLY
3. NO screen/hardware/WebGL overrides (AdsPower handles at C++)
4. NO `__pw*` deletion (corrupts rebrowser internals)
5. Test on fresh profile
