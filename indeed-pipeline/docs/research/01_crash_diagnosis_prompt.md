# Perplexity Research #1 — Why is add_init_script crashing the browser?

> Prompt sent: 2026-03-13 ~23:26 CST
> Source: rag_debug_prompt.md

## Prompt Summary
Full environment specs (Ubuntu 24.04, Python 3.12, rebrowser-playwright 1.52.0, Chrome 134, AdsPower headless, Xvfb :99). Asked why `context.add_init_script()` with `Object.defineProperty` overrides on screen, navigator, WebGL, and Playwright internals causes silent Chrome renderer crash after first `page.goto()`.

## Key Findings

1. **`alwaysIsolated` mode** runs ALL init script code in a separate isolated JS context — NOT in the main page world
2. **`delete window.__playwright__binding__`** and **`delete window.__pwInitScripts`** attack rebrowser-patches' own internal bookkeeping in the isolated world, corrupting the runtime
3. **WebGL prototype double-patching** conflicts with AdsPower's C++ level hooks — confirmed crash trigger
4. **Screen/hardware `Object.defineProperty` overrides** are redundant — AdsPower already handles at engine level, and they only affect isolated world anyway
5. **Recommended fix:** Strip to `navigator.webdriver = undefined` only, or switch to `addBinding` mode

## Action Taken
Stripped init script to webdriver-only. Browser survived navigation (confirmed).
