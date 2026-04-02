# Deep Research Prompt — Maximum Stealth Browser Automation
## Topic: nodriver + Playwright Hybrid Architecture for Anti-Bot Bypass

---

## Context (read fully before researching)

I am building a fully automated job application pipeline that:
- Uses **AdsPower** anti-detect browser profiles (handles TLS/JA3 fingerprint, WebGL/Canvas spoofing, navigator properties, residential SOCKS5 proxies, persistent cookie sessions)
- Connects to AdsPower browsers via **Chrome DevTools Protocol (CDP)** using Python
- Must navigate **Indeed.com** (which uses both **Cloudflare** and **PerimeterX / HUMAN Security** behavioral analytics)
- Must fill out **SmartApply** forms (dynamic multi-step application forms on `smartapply.indeed.com`)
- Uses **Gemini Vision** (screenshot → LLM → JSON action) to decide form actions — no hardcoded selectors

**Current stack:**
- `playwright` Python (`connect_over_cdp()`) for browser control
- `google-genai` (Gemini 2.5 Flash) for form-filling decisions
- `nodriver` (Python, by ultrafunkamsterdam) was previously used and archived

**The problem:**
The current playwright implementation connects to AdsPower via CDP and navigates Indeed, but human behavioral simulation is minimal:
- Mouse never moves between page loads
- Scroll uses `window.scrollBy()` (JS injection) — not a real OS wheel event
- No hover before clicking elements
- No natural cursor trajectory (linear teleport, not bezier curve)
- Warmup is only 5–10s of idle time with no interaction

PerimeterX (used by Indeed) scores behavioral signals including: mouse entropy, scroll physics, click trajectory, event timing jitter, and isTrusted event properties. Cloudflare scores TLS fingerprint + IP reputation (handled by AdsPower). The behavioral layer is the remaining gap.

---

## What I Need Researched

### Approach B: Port nodriver behavior signatures into Playwright

**Research questions:**

1. **CDP mouse event accuracy**: When playwright sends `Input.dispatchMouseEvent` via `connect_over_cdp()`, does the JS event object receive `isTrusted = true`? Does this differ from when playwright is launched directly (not via CDP attach)?

2. **`page.mouse.wheel()` vs `window.scrollBy()`**: At the CDP level, what is the actual difference? Does `page.mouse.wheel()` generate a real `WheelEvent` with `isTrusted = true` and proper `deltaMode`? Does PerimeterX distinguish these?

3. **Bezier curve mouse movement**: What is the most accurate Python implementation of Fitts's Law / bezier curve mouse paths using playwright's `page.mouse.move()`? Is there an existing library (e.g., `pyautogui` curves ported to CDP)? What granularity of intermediate points is needed to fool ML-based movement analysis?

4. **Sub-millisecond timing jitter**: Real hardware HID events have physical timing noise. Can this be replicated in CDP? Are there techniques (e.g., inserting `asyncio.sleep(random.gauss(0.012, 0.003))` between `mouse.move()` calls) that approximate hardware jitter convincingly?

5. **nodriver's specific implementation**: What does `uc.Tab.scroll_down()` actually send at the CDP level? What does `element.mouse_move()` do differently from `page.mouse.move()` in playwright? Is there a technical behavioral difference or are they identical CDP commands?

6. **Playwright CDP attach vs direct launch**: When using `playwright.connect_over_cdp()` on an existing browser (not playwright-launched), does playwright inject `__playwright_binding__`, `__playwright_evaluation_script__`, or any other detectable artifacts into page context? What exactly is injected vs not injected? Can PerimeterX or Cloudflare detect playwright via these artifacts when connecting over CDP?

7. **Mouse click precision**: Real humans click with ~3–8px offset from element center due to motor imprecision. Does PerimeterX track this? What is the recommended approach for imprecise clicking in playwright?

8. **`page.hover()` vs `page.mouse.move()` + `page.click()`**: Which is stealthier? Does `page.hover()` generate intermediate mouse move events or just one `mouseover` event?

---

### Approach C: nodriver wrapper + playwright apply engine (sequential handoff)

**Research questions:**

1. **CDP session handoff**: Is it safe to have nodriver connect to a CDP port, do its work, disconnect, then have playwright connect to the SAME port on the same running browser? What happens to the browser state (cookies, navigation, open pages) between connections?

2. **nodriver disconnection without browser close**: When calling `browser.stop()` on a nodriver `Browser` instance that was created via `Browser.create(host=, port=)` (attached, not launched), does nodriver send `Browser.close` over CDP (which kills the browser process) or does it just close the WebSocket connection cleanly? Is there a way to force clean WebSocket disconnect without CDP browser teardown?

3. **Multiple simultaneous CDP clients**: Can nodriver and playwright both hold an open CDP connection to the same browser at the same time? What are the risks (command conflicts, event listener conflicts, session state corruption)?

4. **Tab state preservation**: If nodriver navigates tab[1] to SmartApply and then disconnects, will playwright's `connect_over_cdp()` see that same tab at `context.pages[1]` with the same URL and DOM state? Or is there risk of page reload?

5. **nodriver's anti-detection specific features**: Does nodriver do anything at browser launch or attach time that modifies the browser's fingerprint, patches JS properties, or injects any scripts that playwright does NOT do? If nodriver's only advantage is behavioral (human timing), is there any other secret sauce?

6. **Recommended handoff architecture**: Given the above, what is the safest implementation pattern for:
   - nodriver handling warmup + navigation + smashing the Apply button
   - playwright taking over for the multi-step SmartApply form
   - Without closing the browser between the two

---

### General Stealth Research

1. **PerimeterX behavioral fingerprinting in 2025–2026**: What behavioral signals does PerimeterX v4+ specifically collect on Indeed? Are there public postmortems, security research papers, or reverse engineering writeups about their JS collector?

2. **Playwright stealth in CDP attach mode**: Are there known stealth patches (like `playwright-stealth` for direct-launch mode) that also work when connecting via `connect_over_cdp()`? What JS properties does PerimeterX check that differ between a real Chrome user and a CDP-controlled session?

3. **AdsPower + playwright combination**: Are there known public implementations, GitHub repos, or writeups of `playwright.connect_over_cdp()` attaching to AdsPower specifically? What are the known pitfalls?

4. **Best-in-class human simulation libraries (Python)**: What are the current top libraries or techniques for:
   - Bezier curve mouse movement via CDP
   - Realistic scroll simulation
   - Natural typing (beyond simple per-char delays)
   Is `playwright-stealth` (PyPI) compatible with CDP attach mode?

5. **Indeed-specific bot detection (2025)**: Beyond Cloudflare and PerimeterX, does Indeed run its own behavioral analytics or custom anti-bot? Are there reports of what specifically triggers "suspicious activity" warnings on Indeed job applications?

---

## Constraints & Requirements

- **Python only** — no TypeScript, no Node.js in the pipeline
- **AdsPower is non-negotiable** — handles fingerprinting, must use its CDP port
- **Must not close or restart the browser** — sessions must be preserved
- **VPS deployment** — runs headless, no display, no real mouse hardware available
- **Cannot use undetected-chromedriver** launch approach — browser is already running via AdsPower
- **Goal**: Navigate Indeed homepage → job page → click Apply → fill SmartApply → submit, with behavioral profile indistinguishable from a slow, slightly distracted human

---

## Desired Output Format

For each research question, provide:
1. **Direct technical answer** (what actually happens at CDP/JS level)
2. **Confidence level** (high / medium / low — based on documentation vs inference)
3. **Source** (CDP spec, playwright source, PerimeterX research, etc.)
4. **Implementation recommendation** (concrete Python code snippet if applicable)

Final section: **Recommended Architecture** — given everything researched, which approach (B or C, or a variant) gives maximum stealth with minimum implementation risk? Include a complete pseudocode flow of the recommended implementation.
