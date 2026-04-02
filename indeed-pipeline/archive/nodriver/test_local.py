#!/usr/bin/env python3
"""
M10 stress test — full human-like Indeed session, local, no apply submitted.
Profiles fetched from Supabase. Rotates on Cloudflare/login detection.

Flow:
  1. Fetch profiles from Supabase adspower_profiles (cookie_status=success)
  2. Start AdsPower profile, attach nodriver (single tab)
  3. Land on indeed.com, idle like a human arriving
  4. Observe page state — rotate immediately if Cloudflare/login
  5. Scroll homepage, type search query per-character
  6. Observe search results — rotate if Cloudflare/login
  7. Scroll results, pick a job, click it
  8. Read job page (scroll, pause)
  9. Click "Apply now" — STOP, do not submit form
  10. Stay open until you press Enter
"""
import asyncio
import random
import re

import requests
import nodriver as uc

ADSPOWER_BASE = "http://localhost:50325"
ADSPOWER_API_KEY = "6690380481d7de70c40230dca72e9403005bda7f364e3e6f"

SUPABASE_URL = "https://uckkgnqlehprbpypcgjc.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVja2tnbnFsZWhwcmJweXBjZ2pjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0Nzg3NTQsImV4cCI6MjA4NzA1NDc1NH0"
    ".Wf8n2ZNSoT429QAdC3xWAtTaklwUO14z7pX7_6C-Sgw"
)
SUPA_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

SEARCH_QUERY = "Phone Receptionist"
SEARCH_LOCATION = "California"


# ── Supabase ──────────────────────────────────────────────────────────────────

def fetch_profiles() -> list[dict]:
    """Fetch active AdsPower profiles from Supabase, ordered by account_slot."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/adspower_profiles",
        params={
            "cookie_status": "eq.success",
            "order": "account_slot.asc",
            "select": "user_id,account_slot,email,profile_name",
        },
        headers=SUPA_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ── AdsPower ──────────────────────────────────────────────────────────────────

def start_profile(user_id: str) -> dict:
    resp = requests.get(
        f"{ADSPOWER_BASE}/api/v1/browser/start",
        params={"user_id": user_id, "api_key": ADSPOWER_API_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"AdsPower start failed: {data}")
    return data["data"]


def stop_profile(user_id: str):
    try:
        requests.get(
            f"{ADSPOWER_BASE}/api/v1/browser/stop",
            params={"user_id": user_id, "api_key": ADSPOWER_API_KEY},
            timeout=10,
        )
        print("[AdsPower] Profile stopped.")
    except Exception as e:
        print(f"[AdsPower] Stop error (non-fatal): {e}")


# ── Human-like helpers ────────────────────────────────────────────────────────

async def delay(min_s: float, max_s: float):
    base = random.uniform(min_s, max_s)
    noise = random.gauss(0, 0.1)
    await asyncio.sleep(max(0.05, base + noise))


async def human_type(element, text: str):
    await element.click()
    await delay(0.3, 0.6)
    for char in text:
        await element.send_keys(char)
        await asyncio.sleep(random.uniform(0.07, 0.22))


async def human_scroll(page, steps: int = 3):
    for _ in range(steps):
        pixels = random.randint(200, 450)
        await page.scroll_down(pixels)
        await delay(0.7, 2.0)


async def human_click(element):
    """Scroll into view, hover 0.8–1.5s (simulate mouse settling), then click."""
    await element.scroll_into_view()
    await delay(0.8, 1.5)
    await element.click()
    await delay(0.3, 0.6)


# ── Page state detection ──────────────────────────────────────────────────────

def detect_page_state(content: str) -> str:
    """Classify what Indeed is currently showing based on page content."""
    cl = content.lower()
    if (
        "cf-challenge" in cl
        or "turnstile" in cl
        or "verify you are human" in cl
        or ("captcha" in cl and "challenge" in cl)
        or "ray id" in cl
    ):
        return "cloudflare"
    if "are you a robot" in cl or ("captcha" in cl and "verify" in cl):
        return "captcha"
    if (
        "sign in to indeed" in cl
        or "sign in with google" in cl
        or ("sign in" in cl and "create an account" in cl)
    ):
        return "login_required"
    if 'data-jk="' in content or '"jk":' in content or "jobs found" in cl:
        return "search_results"
    if "apply now" in cl or "easy apply" in cl or "apply on company site" in cl:
        return "job_page"
    return "unknown"


# ── Session runner ────────────────────────────────────────────────────────────

async def run_session(profile: dict) -> str:
    """
    Run one full test session with the given AdsPower profile.
    Returns: 'success' | 'cloudflare' | 'captcha' | 'login_required' | 'no_jobs' | 'error'

    Cloudflare strategy: if CF challenge appears at any point, stop and rotate.
    Never attempt to click Turnstile — it always rejects programmatic clicks.
    Prevention is the only bypass: valid session cookies + natural navigation.
    """
    user_id = profile["user_id"]
    email = profile.get("email", "?")

    print(f"\n{'='*60}")
    print(f"Profile : {profile.get('profile_name')} ({email})")
    print(f"user_id : {user_id}")
    print(f"{'='*60}")

    print("\n[1] Starting AdsPower profile...")
    try:
        profile_data = start_profile(user_id)
    except Exception as e:
        print(f"[!] Could not start profile: {e}")
        return "error"

    debug_port = int(profile_data["debug_port"])
    print(f"[1] debug_port: {debug_port}")

    try:
        print(f"\n[2] Attaching nodriver (port {debug_port})...")
        browser = await uc.Browser.create(host="127.0.0.1", port=debug_port)
        tabs = browser.tabs
        print(f"[2] Open tabs: {len(tabs)} — closing extras")
        for tab in tabs[1:]:
            await tab.close()
            await asyncio.sleep(0.3)
        page = tabs[0]
        print("[2] Attached, single tab ready")

        # ── Step 3: Homepage warmup ───────────────────────────────────────────
        print("\n[3] Landing on indeed.com (warmup)...")
        await page.get("https://www.indeed.com")
        idle = random.uniform(8, 15)
        print(f"[3] Idling {idle:.1f}s on homepage...")
        await asyncio.sleep(idle)

        content = await page.get_content()
        state = detect_page_state(content)
        print(f"[3] Page state: {state}")

        if state in ("cloudflare", "captcha"):
            print(f"[!] {state} on homepage — rotating profile")
            return state
        if state == "login_required":
            print("[!] No saved session in this profile — rotating")
            return "login_required"

        # Scroll homepage like a human reading it
        await human_scroll(page, steps=random.randint(2, 3))
        await delay(3.0, 6.0)

        # ── Step 4: Search ────────────────────────────────────────────────────
        print(f"\n[4] Typing search: '{SEARCH_QUERY}' in '{SEARCH_LOCATION}'...")
        what_box = None
        for selector in [
            "input#text-input-what",
            "input[name='q']",
            "input[aria-label='What']",
            "[data-testid='search-what-input']",
            "input[placeholder*='job title']",
            "input[placeholder*='Job title']",
        ]:
            what_box = await page.select(selector, timeout=3)
            if what_box:
                print(f"[4] Search box found via: {selector}")
                break

        if what_box:
            await what_box.click()
            await delay(0.3, 0.6)
            await what_box.send_keys("\ue009a")  # Ctrl+A to clear
            await human_type(what_box, SEARCH_QUERY)

            where_box = None
            for sel in [
                "input#text-input-where",
                "input[aria-label='Where']",
                "input[name='l']",
            ]:
                where_box = await page.select(sel, timeout=3)
                if where_box:
                    break
            if where_box:
                await where_box.click()
                await delay(0.2, 0.5)
                await where_box.send_keys("\ue009a")
                await human_type(where_box, SEARCH_LOCATION)

            await delay(0.5, 1.2)
            search_btn = await page.select("button[type='submit']", timeout=3)
            if search_btn:
                await human_click(search_btn)
            else:
                await what_box.send_keys("\n")
        else:
            # Direct URL fallback — add extra delay to look less robotic
            print("[!] Search box not found — navigating directly (extra 10s delay)")
            await delay(10.0, 15.0)
            search_url = (
                "https://www.indeed.com/jobs"
                f"?q={SEARCH_QUERY.replace(' ', '+')}"
                f"&l={SEARCH_LOCATION.replace(' ', '+')}"
            )
            await page.get(search_url)

        # ── Observe after search ──────────────────────────────────────────────
        await delay(5.0, 8.0)
        content = await page.get_content()
        state = detect_page_state(content)
        print(f"[4] Page state after search: {state}")

        if state in ("cloudflare", "captcha"):
            print(f"[!] {state} on search page — rotating")
            return state
        if state == "login_required":
            print("[!] Lost session after search — rotating")
            return "login_required"

        # ── Step 5: Browse results ────────────────────────────────────────────
        print("\n[5] Browsing search results...")
        await human_scroll(page, steps=random.randint(3, 5))
        await delay(4.0, 8.0)

        jk_list = re.findall(r'data-jk="([a-f0-9]{16})"', content)
        if not jk_list:
            jk_list = re.findall(r'"jk"\s*:\s*"([a-f0-9]{16})"', content)
        jk_list = list(dict.fromkeys(jk_list))
        print(f"[5] Found {len(jk_list)} job IDs")

        if not jk_list:
            print("[!] No job IDs found")
            return "no_jobs"

        pick = min(random.randint(0, 2), len(jk_list) - 1)
        chosen_jk = jk_list[pick]
        print(f"[5] Clicking job #{pick + 1}: jk={chosen_jk}")

        job_card = await page.find(chosen_jk, timeout=5)
        if job_card:
            await human_click(job_card)
            await delay(3.0, 5.0)
        else:
            await page.get(f"https://www.indeed.com/viewjob?jk={chosen_jk}")
            await delay(3.0, 5.0)

        # ── Step 6: Read job page ─────────────────────────────────────────────
        print("\n[6] Reading job page...")
        await human_scroll(page, steps=random.randint(3, 5))
        read_time = random.uniform(10, 22)
        print(f"[6] Reading for {read_time:.1f}s...")
        await asyncio.sleep(read_time)

        content = await page.get_content()
        state = detect_page_state(content)

        signin_present = "sign in to indeed" in content.lower()
        apply_present = any(
            lbl.lower() in content.lower()
            for lbl in ["Apply now", "Easy Apply", "Apply on company site"]
        )
        email_match = re.search(r'"email"\s*:\s*"([^"]+@[^"]+)"', content)
        name_match = re.search(r'"displayName"\s*:\s*"([^"]+)"', content)

        print("\n[6] Page state:")
        print(f"  Logged in:    {'✅ YES' if not signin_present else '❌ NO'}")
        if name_match:  print(f"  Account:      {name_match.group(1)}")
        if email_match: print(f"  Email:        {email_match.group(1)}")
        print(f"  Apply button: {'✅ YES' if apply_present else '❌ NOT FOUND'}")
        print(f"  State:        {state}")

        if state in ("cloudflare", "captcha", "login_required"):
            print(f"[!] {state} on job page — rotating")
            return state

        # ── Step 7: Click Apply (no submit) ───────────────────────────────────
        if apply_present:
            print("\n[7] Clicking Apply now (will NOT submit form)...")
            for label in ["Apply now", "Easy Apply", "Apply on company site"]:
                btn = await page.find(label, best_match=True, timeout=5)
                if btn:
                    await delay(2.0, 4.0)
                    await human_click(btn)
                    print(f"[7] Clicked: '{label}'")
                    await delay(3.0, 5.0)
                    break
        else:
            print("\n[7] No Apply button — inspect browser to see what's on screen")

        print("\n" + "=" * 60)
        print("M10 COMPLETE — browser staying open for inspection")
        print("Press Enter to stop profile and close browser...")
        print("=" * 60)
        input()
        return "success"

    except Exception as e:
        print(f"\n[!] Unexpected error: {e}")
        return "error"
    finally:
        stop_profile(user_id)


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("M10 STRESS TEST — human-like Indeed session (no submit)")
    print("Profiles: Supabase  |  CF strategy: rotate, never click")
    print("=" * 60)

    print("\n[0] Fetching profiles from Supabase...")
    profiles = fetch_profiles()
    print(f"[0] {len(profiles)} profiles loaded:")
    for p in profiles:
        print(f"    slot {p['account_slot']}: {p['user_id']} — {p.get('email', '?')}")

    for i, profile in enumerate(profiles):
        print(f"\n--- Attempt {i + 1}/{len(profiles)} ---")
        result = await run_session(profile)

        if result == "success":
            print(f"\n✅ Session complete with profile {profile['user_id']}")
            break
        else:
            print(f"[!] Rotating ({result}) — trying next profile")
            await asyncio.sleep(3)
    else:
        print("\n❌ All profiles exhausted without a clean session")


if __name__ == "__main__":
    asyncio.run(main())
