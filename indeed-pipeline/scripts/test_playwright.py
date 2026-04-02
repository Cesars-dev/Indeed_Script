"""
Local test: playwright + AdsPower CDP connection → navigate to Indeed job URL.

Run: venv_local/bin/python3.13 scripts/test_playwright.py

What this tests:
  1. playwright can connect to AdsPower browser via CDP (through Mac tunnel port 50325)
  2. Navigate to a job URL
  3. Take a screenshot so we can see the page state
  4. Verify we're logged in (checks for account name / signed-in indicators)

Requirements:
  - AdsPower running on Mac (port 50325 via tunnel if on VPS, or direct if on Mac)
  - Profile k19td50a started manually in AdsPower before running this script
  - Or set ADSPOWER_PROFILE_ID env var to auto-start via API
"""

import asyncio
import os
import sys
import time

import requests
from playwright.async_api import async_playwright

# ── Config ──────────────────────────────────────────────────────────────────
ADSPOWER_HOST = os.getenv("ADSPOWER_HOST", "http://127.0.0.1")
ADSPOWER_PORT = int(os.getenv("ADSPOWER_PORT", "50325"))
ADSPOWER_API_KEY = os.getenv("ADSPOWER_API_KEY", "")
PROFILE_ID = os.getenv("ADSPOWER_PROFILE_ID", "k19td50a")  # account 10

TEST_URL = (
    "https://www.indeed.com/viewjob"
    "?tk=1ji58qvqok8i580b&jk=58446c601423ff56&from=sj&jr=1"
    "&ad=-6NYlbfkN0ArwtD7yds-2s2Ba_fYYp1sbYG1hnxrMenz5mC1-sbtMc_-70DbsKzzwUSJZctCFbrExzFi7UMpY1vevch0-2-5gfxNsG5kNHze6Nw0USzmr9s_qvndPh84CWsMWbMDyiQaL9PdrlLXm1pSV5tCCaZg5b1OI4XIkcR1kJ8Lg9xVtFEg6jO3atV3rwUa8lnAjs0OcEU93tG-gtAgD56rLXVGyZDOw7Gtc1SX13WlAamAKZ5nXlWWrzTGWklALb6yKVFKuLzgmg4U3QWi6bZcR95O_57CyAd1kOfkr1c5EOwFsV7J1LXIWjg0v72z1NVuQEIuxzTophfRsHC7TrOP06yh4BJcKQE7P1mV7dRWrAyKPRSDBLLDuks1R1LZnVKrfCppEDu4dZ9j93yRFbaepJT2xmbLSglgvOwJ-ODspej5Jxzz5597lMza9n4vO7gl3jwrZ0gWPETm08x0T-SN4H4z5Hsv32T-QmZw4UmDes0n16w-YaANuD7XMQitt6bmaV9bKekcnhTRCaAa8RKJNHzH1tVBj-Fg_K13Vi7DPp9T-SNnavZZc6j3nAe-n5GnpsthHz4MjxGAX3CUVPHXJ_e05busGJTiAE8%3D"
    "&advn=5348092899229628&xkcb=SoA96_M3mFZkJXxbtZ0UbzkdCdPP"
    "&xpse=SoAg6_I3mFZjTyWTXx0PbzkdCdPP&vjs=3"
)

SCREENSHOT_DIR = "/tmp/playwright_test"

# ── AdsPower helpers ─────────────────────────────────────────────────────────

def _api(path: str, params: dict = None):
    base = f"{ADSPOWER_HOST}:{ADSPOWER_PORT}"
    p = params or {}
    if ADSPOWER_API_KEY:
        p["serial_number"] = ADSPOWER_API_KEY  # some builds use serial_number
    r = requests.get(f"{base}{path}", params=p, timeout=15)
    r.raise_for_status()
    return r.json()


def start_profile(user_id: str) -> str:
    """Start AdsPower profile, return CDP debug URL."""
    data = _api("/api/v1/browser/start", {"user_id": user_id, "open_tabs": 1})
    if data.get("code") != 0:
        raise RuntimeError(f"AdsPower start failed: {data}")
    ws = data["data"].get("ws", {}).get("puppeteer", "")
    debug_port = data["data"].get("debug_port", "")
    print(f"[adspower] started profile {user_id} → port {debug_port}, ws={ws}")
    return ws, debug_port


def stop_profile(user_id: str):
    try:
        _api("/api/v1/browser/stop", {"user_id": user_id})
        print(f"[adspower] stopped profile {user_id}")
    except Exception as e:
        print(f"[adspower] stop error (ok to ignore): {e}")


# ── Main test ─────────────────────────────────────────────────────────────────

async def run_test():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Playwright local test")
    print(f"Profile: {PROFILE_ID}")
    print(f"URL: {TEST_URL[:80]}...")
    print(f"Screenshots → {SCREENSHOT_DIR}/")
    print(f"{'='*60}\n")

    # 1. Start AdsPower profile
    print("[1] Starting AdsPower profile...")
    try:
        ws_endpoint, debug_port = start_profile(PROFILE_ID)
    except Exception as e:
        print(f"[FAIL] Could not start AdsPower profile: {e}")
        print("Make sure AdsPower is running and the tunnel is active (port 50325).")
        sys.exit(1)

    await asyncio.sleep(3)  # let browser settle

    cdp_url = f"http://127.0.0.1:{debug_port}"
    print(f"[2] Connecting playwright to CDP: {cdp_url}")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(cdp_url, timeout=15000)
        except Exception as e:
            print(f"[FAIL] CDP connect failed: {e}")
            stop_profile(PROFILE_ID)
            sys.exit(1)

        print(f"[3] Connected. Browser version: {browser.version}")

        # Get existing context / page
        contexts = browser.contexts
        if not contexts:
            context = await browser.new_context()
        else:
            context = contexts[0]

        # Always open a fresh tab — leave existing tabs untouched
        page = await context.new_page()
        print(f"[3b] Opened new tab (total tabs: {len(context.pages)})")

        print(f"[4] Navigating to Indeed job URL...")
        try:
            await page.goto(TEST_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[WARN] Navigation error (continuing): {e}")

        title = await page.title()
        url = page.url
        print(f"[5] Page title: {title}")
        print(f"    Current URL: {url[:100]}")

        # Screenshot
        ts = int(time.time())
        shot_path = f"{SCREENSHOT_DIR}/test_{ts}.png"
        await page.screenshot(path=shot_path, full_page=False)
        print(f"[6] Screenshot saved: {shot_path}")

        # Basic checks
        content = await page.content()
        logged_in = any(x in content.lower() for x in ["sign out", "my jobs", "profile", "resume"])
        cf_blocked = "just a moment" in title.lower() or "cloudflare" in title.lower()

        print(f"\n{'='*60}")
        print(f"Results:")
        print(f"  Logged in signals: {'YES' if logged_in else 'NO'}")
        print(f"  CF blocked:        {'YES — need manual bypass' if cf_blocked else 'NO'}")
        print(f"  Apply button:      ", end="")

        apply_btn = await page.query_selector("[data-testid='indeedApplyButton'], .ia-IndeedApplyButton, #indeedApplyButton")
        if apply_btn:
            print("FOUND ✓")
        else:
            # fallback text search
            try:
                apply_btn = await page.get_by_text("Apply with Indeed", exact=False).first.element_handle(timeout=2000)
                print("FOUND via text ✓")
            except Exception:
                print("NOT FOUND")

        print(f"{'='*60}\n")

        await asyncio.sleep(2)
        await browser.close()

    # Stop profile
    stop_profile(PROFILE_ID)
    print("\nTest complete.")


if __name__ == "__main__":
    asyncio.run(run_test())
