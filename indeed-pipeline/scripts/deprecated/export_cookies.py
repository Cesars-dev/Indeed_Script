#!/usr/bin/env python3
"""
Automated cookie exporter — opens each AdsPower profile, logs into Indeed
via Google (types email + password), waits for session to settle, saves cookies.

Profiles fetched from Supabase adspower_profiles (ordered by account_slot).
Passwords matched by email from config/accounts.json — no positional guessing.

Usage:
  python3.13 -u scripts/export_cookies.py            # all 10 profiles
  python3.13 -u scripts/export_cookies.py --slot 1   # single slot
"""
import argparse
import asyncio
import json
import os
import sys
import time
import random
import requests
from playwright.async_api import async_playwright

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADSPOWER_API  = "http://local.adspower.net:50325"
COOKIES_DIR   = os.path.join(BASE_DIR, "config", "cookies")
ACCOUNTS_FILE = os.path.join(BASE_DIR, "config", "accounts.json")
os.makedirs(COOKIES_DIR, exist_ok=True)

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

SESSION_COOKIES = {"JSESSIONID", "INDEED_CSRF_TOKEN"}


def fetch_profiles() -> list[dict]:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/adspower_profiles",
        params={"select": "user_id,account_slot,email,profile_name",
                "order": "account_slot.asc"},
        headers=SUPA_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def load_passwords() -> dict[str, str]:
    with open(ACCOUNTS_FILE) as f:
        accounts = json.load(f)
    return {a["email"]: a["password"] for a in accounts}


def start_profile(user_id: str) -> dict:
    requests.get(f"{ADSPOWER_API}/api/v1/browser/stop",
                 params={"user_id": user_id}, timeout=10)
    time.sleep(random.uniform(5, 8))
    r = requests.get(f"{ADSPOWER_API}/api/v1/browser/start",
                     params={"user_id": user_id, "headless": "0"}, timeout=30)
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Failed to start profile {user_id}: {data}")
    return data["data"]


def stop_profile(user_id: str):
    requests.get(f"{ADSPOWER_API}/api/v1/browser/stop",
                 params={"user_id": user_id}, timeout=10)


async def login_and_export(slot: int, user_id: str, email: str, password: str) -> bool:
    print(f"\n[slot {slot}] Starting profile {user_id} for {email}...")
    browser_data = start_profile(user_id)
    ws_url = browser_data.get("ws", {}).get("puppeteer")

    if not ws_url:
        print(f"[slot {slot}] No WebSocket URL — skipping")
        return False

    print(f"[slot {slot}] Connecting via CDP...")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(ws_url, timeout=30000)
            await asyncio.sleep(5)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            pages   = context.pages
            page    = pages[0] if pages else await context.new_page()

            # Warm up on google.com first before hitting indeed.com
            await page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(random.uniform(5, 8))

            await page.goto("https://www.indeed.com", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(3, 5))

            content = await page.content()
            if "Sign in" not in content:
                print(f"[slot {slot}] Already logged in — grabbing cookies")
            else:
                # Click Sign in button
                try:
                    await page.click(
                        "a[href*='account/login'], button[data-gnav-element-name='SignIn']",
                        timeout=5000)
                    await asyncio.sleep(2)
                except Exception:
                    pass

                # Click Google sign-in (may open popup)
                try:
                    await page.wait_for_selector(
                        "button[data-tn-element='googleButton'], [data-testid='google-login-button']",
                        timeout=5000)
                    async with context.expect_page() as popup_info:
                        await page.click(
                            "button[data-tn-element='googleButton'], [data-testid='google-login-button']")
                    google_page = await popup_info.value
                    await google_page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(2)
                except Exception:
                    google_page = page

                # Type email
                try:
                    await google_page.wait_for_selector("input[type='email']", timeout=8000)
                    await google_page.type("input[type='email']", email, delay=80)
                    await asyncio.sleep(1)
                    await google_page.keyboard.press("Enter")
                    await asyncio.sleep(3)
                except Exception:
                    pass

                # Type password
                try:
                    await google_page.wait_for_selector("input[type='password']", timeout=8000)
                    await google_page.type("input[type='password']", password, delay=80)
                    await asyncio.sleep(1)
                    await google_page.keyboard.press("Enter")
                    await asyncio.sleep(4)
                except Exception:
                    pass

            # Wait for Cloudflare + login to fully settle
            print(f"[slot {slot}] Waiting 60s for Cloudflare/session to settle...")
            await asyncio.sleep(60)

            # Grab cookies from all contexts
            all_cookies = []
            for ctx in browser.contexts:
                try:
                    all_cookies.extend(await ctx.cookies())
                except Exception:
                    pass

            indeed_cookies = [c for c in all_cookies if "indeed.com" in c.get("domain", "")]
            if not indeed_cookies:
                print(f"[slot {slot}] No Indeed cookies — login failed")
                return False

            found_session = any(c.get("name") in SESSION_COOKIES for c in indeed_cookies)
            if not found_session:
                print(f"[slot {slot}] Only tracking cookies — session incomplete")
                return False

            print(f"[slot {slot}] Session cookie confirmed ✓")
            out = os.path.join(COOKIES_DIR, f"account_{slot}.json")
            with open(out, "w") as f:
                json.dump(indeed_cookies, f, indent=2)
            print(f"[slot {slot}] Saved {len(indeed_cookies)} cookies → {out}")
            return True

    except Exception as e:
        print(f"[slot {slot}] Error: {e}")
        return False
    finally:
        stop_profile(user_id)
        await asyncio.sleep(3)


async def main(only_slot: int | None = None):
    print("Fetching profiles from Supabase...")
    profiles  = fetch_profiles()
    passwords = load_passwords()

    print(f"Found {len(profiles)} profiles:")
    for p in profiles:
        print(f"  slot {p['account_slot']:2d}: {p['user_id']}  {p.get('email','?')}")

    if only_slot is not None:
        profiles = [p for p in profiles if p["account_slot"] == only_slot]
        if not profiles:
            print(f"No profile found for slot {only_slot}")
            sys.exit(1)

    ok = 0
    for p in profiles:
        slot    = p["account_slot"]
        user_id = p["user_id"]
        email   = p.get("email", "")
        pw      = passwords.get(email, "Simonala123")

        existing = os.path.join(COOKIES_DIR, f"account_{slot}.json")
        if os.path.exists(existing):
            print(f"  slot {slot:2d}: ⏭  Already has cookies — skipping")
            ok += 1
            continue

        result  = await login_and_export(slot, user_id, email, pw)
        if result:
            ok += 1

    print(f"\n✓ Done: {ok}/{len(profiles)} cookies saved to config/cookies/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", type=int, default=None,
                        help="Run only a specific account slot (1-10)")
    args = parser.parse_args()
    asyncio.run(main(only_slot=args.slot))
