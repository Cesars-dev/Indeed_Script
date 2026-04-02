# Rebrowser CDP Fix — Step 2: ACTION PLAN

> Exact steps, exact commands, exact code changes.

---

## Step 1: Install rebrowser-patches

```bash
cd /usr/local/lib/python3.12/dist-packages/playwright/driver/package
npm install rebrowser-patches@latest
```

---

## Step 2: Patch Playwright driver

```bash
cd /usr/local/lib/python3.12/dist-packages/playwright/driver/package
npx rebrowser-patches@latest patch --packageName playwright-core
```

---

## Step 3: Verify patch applied

```bash
grep -r "isolatedWorld\|REBROWSER" \
  /usr/local/lib/python3.12/dist-packages/playwright/driver/package/lib/server/chromium/crPage.js \
  | head -5
```

Should show patched code references to `isolatedWorld`.

---

## Step 4: Set env var BEFORE Playwright import

**File:** `playwright_indeed.py`, BEFORE line 22 (`from playwright.async_api import ...`)

```python
# ── Rebrowser: isolate Runtime.enable from main context ──
import os
os.environ["REBROWSER_PATCHES_RUNTIME_FIX_MODE"] = "alwaysIsolated"
```

**Insert at:** Line 14 (right after existing imports, before playwright import on L22)

---

## Step 5: Add `slow_mo=50` to `connect_over_cdp`

**File:** `playwright_indeed.py` L954-956

**Before:**
```python
browser = await pw.chromium.connect_over_cdp(
    f"http://127.0.0.1:{debug_port}", timeout=15000
)
```

**After:**
```python
browser = await pw.chromium.connect_over_cdp(
    f"http://127.0.0.1:{debug_port}", timeout=15000, slow_mo=50
)
```

---

## Step 6: Remove redundant `Runtime.disable` band-aid

**File:** `playwright_indeed.py` L1030-1038

**Remove:**
```python
try:
    cdp = await context.new_cdp_session(context.pages[0] if context.pages else await context.new_page())
    await cdp.send("Runtime.disable")
    await cdp.detach()
except Exception:
    pass
```

The rebrowser patch handles this at the source — Runtime.enable never hits main context, so Runtime.disable is unnecessary.

---

## Step 7: Remove redundant console freeze from init_script

**File:** `playwright_indeed.py` L998-1008

**Remove:**
```javascript
// ── Stealth: protect console from CDP Runtime.enable leak ──
const origConsole = {};
['log', 'warn', 'error', 'info', 'debug'].forEach(method => {
    origConsole[method] = console[method];
    Object.defineProperty(console, method, {
        get: () => origConsole[method],
        set: () => {},
        configurable: false
    });
});
```

This was a band-aid for Runtime.enable — no longer needed with rebrowser patch. **Keep all other stealth patches** (webdriver, screen, GPU, battery, permissions).

---

## Step 8: Verify syntax + test

```bash
python3 -c "import ast; ast.parse(open('src/playwright_indeed.py').read()); print('✅ OK')"
```

---

## Summary of Changes

| File | Change | Lines |
|------|--------|-------|
| `playwright_indeed.py` | Add env var before playwright import | +2 lines at L14 |
| `playwright_indeed.py` | Add `slow_mo=50` to connect_over_cdp | L955 |
| `playwright_indeed.py` | Remove `Runtime.disable` block | -6 lines at L1030-1038 |
| `playwright_indeed.py` | Remove console freeze from init_script | -11 lines at L998-1008 |
| Playwright driver | Patch via rebrowser-patches | External |

**Net change to playwright_indeed.py:** -15 lines (cleaner!)
