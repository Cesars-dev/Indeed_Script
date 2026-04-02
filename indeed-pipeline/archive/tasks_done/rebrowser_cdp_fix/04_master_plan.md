# Rebrowser CDP Fix — Step 4: MASTER PLAN (Preflight Verified)

> All line numbers verified against current code. All gaps resolved. Ready to execute.

---

## Verified Line Numbers (as of 2026-03-13 08:03)

| What | Line | Verified |
|------|------|----------|
| `from playwright.async_api import` | L22 | ✅ |
| `connect_over_cdp(` | L954 | ✅ |
| Console freeze block start | L998 | ✅ |
| Console freeze block end | L1008 | ✅ |
| `Runtime.disable` block start | L1030 | ✅ |
| `Runtime.disable` block end | L1038 | ✅ |
| Playwright driver path | `/usr/local/lib/python3.12/dist-packages/playwright/driver/package/` | ✅ |

---

## Execution Steps (in order)

### Step 1: Install rebrowser-patches
```bash
cd /usr/local/lib/python3.12/dist-packages/playwright/driver/package
sudo npm install rebrowser-patches@latest
```

### Step 2: Patch Playwright driver
```bash
cd /usr/local/lib/python3.12/dist-packages/playwright/driver/package
sudo npx rebrowser-patches@latest patch --packageName playwright-core
```

### Step 3: Verify patch
```bash
grep -c "isolatedWorld\|REBROWSER" \
  /usr/local/lib/python3.12/dist-packages/playwright/driver/package/lib/server/chromium/crPage.js
```
Expected: > 0

### Step 4: Add env var to playwright_indeed.py (L14)
Insert BEFORE line 22:
```python
os.environ["REBROWSER_PATCHES_RUNTIME_FIX_MODE"] = "alwaysIsolated"
```
Note: `os` is imported on L14. Insert after L14, before L22.

### Step 5: Add `slow_mo=50` to connect_over_cdp (L954-956)
```python
browser = await pw.chromium.connect_over_cdp(
    f"http://127.0.0.1:{debug_port}", timeout=15000, slow_mo=50
)
```

### Step 6: Remove console freeze (L998-1008)
Remove this block:
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

### Step 7: Remove Runtime.disable band-aid (L1030-1038)
Remove this block:
```python
            try:
                cdp = await context.new_cdp_session(context.pages[0] if context.pages else await context.new_page())
                await cdp.send("Runtime.disable")
                await cdp.detach()
            except Exception:
                pass
```

### Step 8: Syntax check
```bash
python3 -c "import ast; ast.parse(open('src/playwright_indeed.py').read()); print('✅ OK')"
```

### Step 9: VPS deploy (after local test)
```bash
scp -r indeed-pipeline/src/ root@45.55.90.156:/root/indeed-pipeline/
ssh root@45.55.90.156 "cd /usr/local/lib/python3.12/dist-packages/playwright/driver/package && npm install rebrowser-patches@latest && npx rebrowser-patches@latest patch --packageName playwright-core"
```

### Step 10: Document re-patch requirement
Add to `memory/02_browser_automation.md`:
```
## Rebrowser Patches
After any `pip install --upgrade playwright`, re-run:
cd /usr/local/lib/python3.12/dist-packages/playwright/driver/package
npx rebrowser-patches@latest patch --packageName playwright-core
```

---

## What We Keep (NOT removed)

- `navigator.webdriver` → undefined ✅
- Screen/display spoofing ✅
- GPU renderer spoofing ✅
- Battery API spoofing ✅
- Permissions API fix ✅
- Hardware concurrency spoofing ✅

---

## Open Issues: ZERO

All gaps from cross-reference resolved. Ready to execute.
