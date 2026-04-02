#!/usr/bin/env python3
"""
read_fingerprints.py — Read AdsPower browser fingerprints and upload to Supabase.

Steps:
1. Add 'fingerprint' jsonb column to adspower_profiles (if missing)
2. For each profile in the AdsPower 'indeed' group:
   - Start browser via AdsPower API
   - Connect via Playwright CDP (NO init scripts — raw AdsPower values)
   - page.evaluate() to read real fingerprint
   - Stop browser
   - PATCH fingerprint into Supabase
3. Print summary

Run from Mac only (AdsPower desktop app needed).
"""

import asyncio
import json
import os
import sys
import time
import httpx

# ── Config from env ──────────────────────────────────────────────────────────
from dotenv import load_dotenv

# Load from indeed-pipeline/.env first, then root .env
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.dirname(SCRIPT_DIR)
load_dotenv(os.path.join(PIPELINE_DIR, ".env"))
load_dotenv(os.path.join(os.path.dirname(PIPELINE_DIR), ".env"))

ADSPOWER_BASE = os.getenv("ADSPOWER_BASE", "http://127.0.0.1:50325")
ADSPOWER_API_KEY = os.getenv("ADSPOWER_API_KEY", "")
ADSPOWER_GROUP_ID = os.getenv("ADSPOWER_GROUP_ID", "8765960")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_KEY", "")

# ── Fingerprint JS to evaluate ───────────────────────────────────────────────
FINGERPRINT_JS = """
(() => {
    const result = {
        devicePixelRatio: window.devicePixelRatio,
        screenWidth: screen.width,
        screenHeight: screen.height,
        availWidth: screen.availWidth,
        availHeight: screen.availHeight,
        colorDepth: screen.colorDepth,
        pixelDepth: screen.pixelDepth,
        outerWidth: window.outerWidth,
        outerHeight: window.outerHeight,
        hardwareConcurrency: navigator.hardwareConcurrency,
        deviceMemory: navigator.deviceMemory,
        maxTouchPoints: navigator.maxTouchPoints,
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        webglVendor: null,
        webglRenderer: null,
    };

    // Read WebGL info
    try {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        if (gl) {
            const ext = gl.getExtension('WEBGL_debug_renderer_info');
            if (ext) {
                result.webglVendor = gl.getParameter(ext.UNMASKED_VENDOR_WEBGL);
                result.webglRenderer = gl.getParameter(ext.UNMASKED_RENDERER_WEBGL);
            }
        }
    } catch (e) {}

    return result;
})()
"""


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def get_adspower_profiles() -> list[dict]:
    """Fetch all profiles from AdsPower 'indeed' group."""
    profiles = []
    page = 1
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            url = (
                f"{ADSPOWER_BASE}/api/v1/user/list"
                f"?page={page}&page_size=20"
                f"&api_key={ADSPOWER_API_KEY}"
                f"&group_id={ADSPOWER_GROUP_ID}"
            )
            resp = await client.get(url)
            data = resp.json()
            if data.get("code") != 0:
                log(f"❌ AdsPower API error: {data}")
                break
            batch = data.get("data", {}).get("list", [])
            if not batch:
                break
            profiles.extend(batch)
            page += 1
    return profiles


async def start_browser(user_id: str) -> dict | None:
    """Start an AdsPower browser, return connection info."""
    async with httpx.AsyncClient(timeout=60) as client:
        url = (
            f"{ADSPOWER_BASE}/api/v1/browser/start"
            f"?user_id={user_id}"
            f"&api_key={ADSPOWER_API_KEY}"
            f"&open_tabs=1"
            f"&ip_tab=0"
        )
        resp = await client.get(url)
        data = resp.json()
        if data.get("code") != 0:
            log(f"  ❌ Failed to start {user_id}: {data.get('msg', data)}")
            return None
        return data.get("data", {})


async def stop_browser(user_id: str):
    """Stop an AdsPower browser."""
    async with httpx.AsyncClient(timeout=15) as client:
        url = (
            f"{ADSPOWER_BASE}/api/v1/browser/stop"
            f"?user_id={user_id}"
            f"&api_key={ADSPOWER_API_KEY}"
        )
        try:
            await client.get(url)
        except Exception:
            pass


async def read_fingerprint(user_id: str, ws_endpoint: str) -> dict | None:
    """Connect to browser via CDP, read fingerprint, return dict."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        try:
            from rebrowser_playwright.async_api import async_playwright
        except ImportError:
            log("❌ Neither playwright nor rebrowser-playwright installed!")
            sys.exit(1)

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.connect_over_cdp(ws_endpoint, timeout=30000)
        except Exception as e:
            log(f"  ❌ CDP connect failed for {user_id}: {e}")
            return None

        try:
            # Use the first context/page that AdsPower already opened
            contexts = browser.contexts
            if not contexts:
                log(f"  ⚠️  No contexts for {user_id}, creating one")
                ctx = await browser.new_context()
            else:
                ctx = contexts[0]

            pages = ctx.pages
            if not pages:
                page = await ctx.new_page()
            else:
                page = pages[0]

            # Navigate to blank page to ensure clean evaluate
            await page.goto("about:blank", wait_until="load", timeout=10000)
            await asyncio.sleep(1)

            # Read fingerprint — NO init scripts, raw AdsPower values
            fp = await page.evaluate(FINGERPRINT_JS)
            return fp

        except Exception as e:
            log(f"  ❌ Error reading fingerprint for {user_id}: {e}")
            return None
        finally:
            try:
                await browser.close()
            except Exception:
                pass


async def upload_fingerprint(user_id: str, fingerprint: dict) -> bool:
    """PATCH fingerprint into Supabase adspower_profiles row."""
    url = f"{SUPABASE_URL}/rest/v1/adspower_profiles?user_id=eq.{user_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    body = {"fingerprint": fingerprint}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.patch(url, headers=headers, json=body)
        if resp.status_code in (200, 204):
            return True
        else:
            log(f"  ❌ Supabase PATCH failed for {user_id}: {resp.status_code} {resp.text}")
            return False


async def ensure_fingerprint_column():
    """Check if fingerprint column exists by trying to select it."""
    url = f"{SUPABASE_URL}/rest/v1/adspower_profiles?select=fingerprint&limit=1"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            log("✅ fingerprint column exists")
            return True
        else:
            log(f"⚠️  fingerprint column missing — need to add it via Supabase dashboard")
            log(f"   SQL: ALTER TABLE adspower_profiles ADD COLUMN IF NOT EXISTS fingerprint jsonb DEFAULT '{{}}'::jsonb;")
            return False


async def main():
    log("=" * 60)
    log("AdsPower Fingerprint Reader")
    log("=" * 60)

    # Validate config
    if not ADSPOWER_API_KEY:
        log("❌ ADSPOWER_API_KEY not set"); sys.exit(1)
    if not SUPABASE_URL or not SUPABASE_KEY:
        log("❌ SUPABASE_URL or SUPABASE_KEY not set"); sys.exit(1)

    log(f"AdsPower: {ADSPOWER_BASE}")
    log(f"Supabase: {SUPABASE_URL}")

    # --force flag: re-read all profiles even if they already have fingerprints
    force = "--force" in sys.argv
    if force:
        log("⚡ --force flag: will re-read ALL profiles")

    # Check fingerprint column
    col_exists = await ensure_fingerprint_column()
    if not col_exists:
        log("❌ Cannot proceed without fingerprint column. Add it first.")
        sys.exit(1)

    # Get all profiles
    profiles = await get_adspower_profiles()
    log(f"Found {len(profiles)} AdsPower profiles")

    if not profiles:
        log("❌ No profiles found"); sys.exit(1)

    # Check which profiles already have fingerprints in Supabase
    existing_fps = set()
    if not force:
        try:
            fp_url = f"{SUPABASE_URL}/rest/v1/adspower_profiles?select=user_id,fingerprint&fingerprint=neq.{{}}"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            }
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(fp_url, headers=headers)
                if resp.status_code == 200:
                    for row in resp.json():
                        if row.get("fingerprint") and row["fingerprint"] != {}:
                            existing_fps.add(row["user_id"])
            if existing_fps:
                log(f"⏭️  {len(existing_fps)} profiles already have fingerprints — skipping them (use --force to re-read)")
        except Exception as e:
            log(f"⚠️  Could not check existing fingerprints: {e}")

    results = {"success": 0, "failed": 0, "skipped": 0}
    MAX_RETRIES = 2

    for i, profile in enumerate(profiles):
        user_id = profile["user_id"]
        name = profile.get("name", "unknown")
        log(f"\n[{i+1}/{len(profiles)}] {name} ({user_id})")

        # Skip if already has fingerprint
        if user_id in existing_fps:
            log(f"  ⏭️  Already has fingerprint — skipping")
            results["skipped"] += 1
            continue

        fp = None
        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                log(f"  🔄 Retry {attempt}/{MAX_RETRIES}")

            # Start browser
            log(f"  Starting browser...")
            browser_info = await start_browser(user_id)
            if not browser_info:
                await asyncio.sleep(3)
                continue

            ws_endpoint = browser_info.get("ws", {}).get("puppeteer", "")
            if not ws_endpoint:
                log(f"  ❌ No WebSocket endpoint returned")
                await stop_browser(user_id)
                await asyncio.sleep(3)
                continue

            log(f"  CDP: {ws_endpoint[:80]}...")

            # Wait for browser to fully initialize (increased from 3s)
            await asyncio.sleep(6)

            # Read fingerprint
            log(f"  Reading fingerprint...")
            fp = await read_fingerprint(user_id, ws_endpoint)

            # Stop browser
            log(f"  Stopping browser...")
            await stop_browser(user_id)

            if fp:
                break  # Success — exit retry loop
            await asyncio.sleep(3)  # Brief pause before retry

        if not fp:
            results["failed"] += 1
            continue

        # Upload to Supabase
        log(f"  Uploading to Supabase...")
        ok = await upload_fingerprint(user_id, fp)
        if ok:
            log(f"  ✅ Done — screen={fp.get('screenWidth')}x{fp.get('screenHeight')}, "
                f"DPR={fp.get('devicePixelRatio')}, "
                f"GPU={fp.get('webglRenderer', 'N/A')[:40]}")
            results["success"] += 1
        else:
            results["failed"] += 1

        # Brief pause between profiles to not hammer AdsPower
        if i < len(profiles) - 1:
            await asyncio.sleep(3)

    # Summary
    log(f"\n{'=' * 60}")
    log(f"DONE — ✅ {results['success']} | ❌ {results['failed']} | ⏭️ {results['skipped']}")
    log(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
