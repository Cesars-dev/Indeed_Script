# Rebrowser CDP Fix — Step 3: CROSS-REFERENCE

> Audit ↔ Action Plan comparison. Does the plan address every audit finding?

---

## Audit Finding → Plan Coverage

| Audit Finding | Addressed in Plan? | Step |
|--------------|-------------------|------|
| `Runtime.enable` leaks in main context | ✅ rebrowser-patches isolates it | Steps 1-3 |
| `console.log` overwrite detection by CF | ✅ Isolated world = CF can't see | Step 2 |
| `add_init_script` runs after leak | ✅ Patch fixes at source, init_script still runs (screen/GPU) | Step 7 |
| `Runtime.disable` is a band-aid | ✅ Removed | Step 6 |
| Console freeze conflicts with patch | ✅ Removed | Step 7 |
| No `slow_mo` on CDP connection | ✅ Added `slow_mo=50` | Step 5 |
| Env var must be set before import | ✅ Inserted at L14 | Step 4 |
| VPS also needs patching | ⚠️ Not in plan — needs VPS deploy step | **GAP** |
| Patch breaks on pip upgrade | ⚠️ Not in plan — needs post-upgrade hook | **GAP** |

---

## Gaps Found

### GAP 1: VPS Deployment
The audit mentions VPS needs patching too. The action plan only covers local. Need to add:
```bash
ssh root@45.55.90.156 "cd /usr/local/lib/python3.12/dist-packages/playwright/driver/package && npm install rebrowser-patches@latest && npx rebrowser-patches@latest patch --packageName playwright-core"
```

### GAP 2: Re-patch after Playwright upgrade
The audit warns pip upgrade overwrites patches. Need to document in `memory/` or add a verify-patch script.

**Resolution:** Add both to master plan as Step 9 (VPS deploy) and Step 10 (upgrade protection).

---

## Plan Validity Check

| Plan Step | Supported by Audit? | Risk |
|-----------|---------------------|------|
| Install rebrowser-patches | ✅ Dependency identified | Low |
| Patch playwright driver | ✅ Path verified: `/usr/local/.../playwright/driver/package/` | Low |
| Verify grep for isolatedWorld | ✅ Files identified: crPage.js, crServiceWorker.js, crDevTools.js | Low |
| Set env var before import | ✅ Line 22 is the playwright import | Low |
| Add slow_mo=50 | ✅ L954-956 identified | Low |
| Remove Runtime.disable | ✅ L1030-1038 identified | **Medium — verify line numbers still accurate** |
| Remove console freeze | ✅ L998-1008 identified | **Medium — verify line numbers still accurate** |

---

## Contradictions

None found. Audit and plan are aligned.

---

## Open Items for Master Plan

1. Add VPS deploy step
2. Add re-patch documentation/script
3. Verify line numbers against current file (code was edited since audit)
