# Memory: Fingerprint Sync Session — COMPLETE
> Created 2026-03-13, completed same day

## What Was Done

### Step 1: Supabase Schema ✅
- Added `fingerprint JSONB DEFAULT '{}'` column to `adspower_profiles`
- Migration: `add_fingerprint_column`

### Step 2: Read & Upload Fingerprints ✅
- Script: `scripts/read_fingerprints.py`
- All 19/19 profiles have fingerprint data in Supabase
- Script improvements: skip already-done profiles, retry on failure, 6s browser init wait
- AdsPower API does NOT expose fingerprint config (only write param) — must open browser to read

### Step 3: Dynamic Injection in playwright_indeed.py ✅
- Replaced hardcoded init script (1920×1080, GTX 1060) with dynamic f-string
- Reads from `db_row["fingerprint"]` (the Supabase row loaded at startup)
- Falls back to safe defaults (1440×900, DPR=1, Intel GPU) if no fingerprint data
- Logs which fingerprint is being used per profile
- GPU strings properly escaped for JS single quotes

### Step 4: Bugs Fixed ✅
- **deviceMemory null**: All profiles returned `null` for `navigator.deviceMemory`. Fixed with `fp.get("deviceMemory") or 8` (line 973)
- **3 mobile profiles converted to desktop**: Slots 6 (Android), 17 (iPhone), 18 (iPhone) updated via AdsPower Update API + Supabase

### Step 5: AdsPower API Reference ✅
- Saved to `mcp-stack/adspower/API_REFERENCE.md`
- Key finding: `fingerprint_config` is **write-only** in AdsPower API — can set on create/update, but query endpoints don't return it
- Must open browser via CDP to read actual fingerprint values

## Profile Summary (all 19 desktop)
| Slots | Platform | GPU Type |
|-------|----------|----------|
| 1, 7, 11, 12, 16 | MacIntel | Intel Iris / Apple M1 Pro / Apple M2 / Intel HD |
| 2, 3, 8, 9, 13 | Win32 | NVIDIA GeForce 210/950M, Intel UHD 620/630/610 |
| 4, 5, 10, 14, 15, 18, 19 | Linux x86_64 | Intel Xe / RPL-P / UHD 770 |
| 6 | Win32 (was Android) | Intel UHD 620 |
| 17 | MacIntel (was iPhone) | Apple M2 |

## Data Flow (how it works)
1. VPS starts `playwright_indeed.py` → `_load_profiles()` does `SELECT *` from Supabase
2. Each profile's `fingerprint` JSONB column is cached in `_PROFILES` dict
3. When applying, `db_row["fingerprint"]` is read, values injected into `add_init_script`
4. Data is dynamic per restart — update Supabase, restart pipeline, new values apply

## Key Decision
- AdsPower local API `fingerprint_config` is WRITE-ONLY
- Must open browser via CDP to read actual values
- This is better — we read ACTUAL browser values, not just config

## Next Step
- Deploy updated `src/playwright_indeed.py` to VPS
- Test a job application to verify fingerprint injection works
