# Cross-Reference: Audit ↔ Action Plan

## Does the plan address every issue the audit found?

| Audit Issue | Plan Change | Addressed? |
|------------|-------------|------------|
| L15: `alwaysIsolated` makes init script invisible to CF | Change 1: switch to `addBinding` | ✅ |
| L1014-1025: webdriver patch runs in isolated world | Change 2: replace init script (runs in main world with addBinding) | ✅ |
| Missing Battery API shim | Change 2: included in new init script | ✅ |
| Missing Permissions API normalization | Change 2: included in new init script | ✅ |
| L1027: stale comment references "isolated world" | Change 3: update to "addBinding mode" | ✅ |
| Dead code: `fp_vendor_esc`, `fp_renderer_esc` | Identified but deferred (cosmetic) | ⚠️ Acceptable |

## Does the audit support every change the plan proposes?

| Plan Change | Audit Support | Verified? |
|------------|---------------|-----------|
| Change 1: `alwaysIsolated` → `addBinding` | Audit confirms L15 is the only live code reference | ✅ |
| Change 2: new init script with 3 shims | Audit confirms Battery + Permissions are MISSING, webdriver is ineffective in isolated world | ✅ |
| Change 3: comment update | Audit identifies the stale comment | ✅ |

## Contradictions / Gaps

1. **None found.** Audit and plan are aligned.

2. **Risk re-check:** Will `addBinding` mode + our 3 shims cause the same crash?
   - Crash was caused by: `delete __pw*` internals + WebGL prototype double-patch
   - New script does NOT include any of those
   - `addBinding` is the DEFAULT mode — more tested than `alwaysIsolated`
   - **Risk: LOW**

3. **One thing to verify in preflight:** Does the `import` order still work? The env var on L15 must be set BEFORE `from rebrowser_playwright.async_api import ...` on L16+. Need to confirm line ordering hasn't changed.
