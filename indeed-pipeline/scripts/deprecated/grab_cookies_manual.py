#!/usr/bin/env python3
"""
Manual login helper — opens AdsPower profile, waits for you to log in,
then grabs and saves the cookies. No automation, no typing.

Profiles fetched from Supabase adspower_profiles (ordered by account_slot).
Passwords loaded from config/accounts.json.

Usage:
  python3.13 -u scripts/grab_cookies_manual.py

  Optional: run a single slot only
  python3.13 -u scripts/grab_cookies_manual.py --slot 1
"""
import argparse
import asyncio
import json
import os
import sys
import requests
import time
from playwright.async_api import async_playwright

ADSPOWER_API = "http://local.adspower.net:50325"

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIES_DIR  = os.path.join(BASE_DIR, "config", "cookies")
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
    """Fetch active AdsPower profiles from Supabase, ordered by account_slot."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/adspower_profiles",
        params={
            "select": "user_id,account_slot,email,profile_name",
            "order": "account_slot.asc",
        },
        headers=SUPA_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def load_passwords() -> dict[str, str]:
    """Load email → password mapping from config/accounts.json."""
    with open(ACCOUNTS_FILE) as f:
        accounts = json.load(f)
    return {a["email"]: a["password"] for a in accounts}


def start_profile(user_id: str) -> str:
    requests.get(f"{ADSPOWER_API}/api/v1/browser/stop",
                 params={"user_id": user_id}, timeout=10)
    time.sleep(3)
    r = requests.get(f"{ADSPOWER_API}/api/v1/browser/start",
                     params={"user_id": user_id, "headless": "0"}, timeout=30)
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Failed to start profile {user_id}: {data}")
    return data["data"]["ws"]["puppeteer"]


def stop_profile(user_id: str):
    requests.get(f"{ADSPOWER_API}/api/v1/browser/stop",
                 params={"user_id": user_id}, timeout=10)


async def grab(slot: int, user_id: str, email: str, password: str) -> bool:
    print(f"\n[slot {slot}] Opening browser for {email}  (user_id: {user_id})")
    ws_url = start_profile(user_id)

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(ws_url)
        await asyncio.sleep(3)

        # Warm up: navigate to google.com first so the profile has history before hitting indeed.com
        try:
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            pages = context.pages
            page = pages[0] if pages else await context.new_page()
            await page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(5)
        except Exception:
            pass

        print(f"[slot {slot}] Browser warmed up on google.com")
        print(f"[slot {slot}] Now manually: go to indeed.com → Sign in → Google")
        print(f"[slot {slot}]   Email   : {email}")
        print(f"[slot {slot}]   Password: {password}")
        print(f"[slot {slot}] Waiting up to 120s — saves automatically when session detected...")

        # Poll every 10s, exit early once session found
        indeed_cookies: list = []
        found_session = False
        for i in range(12):  # 12 × 10s = 120s max
            await asyncio.sleep(10)
            all_cookies: list = []
            for ctx in browser.contexts:
                try:
                    all_cookies.extend(await ctx.cookies())
                except Exception:
                    pass
            indeed_cookies = [c for c in all_cookies if "indeed.com" in c.get("domain", "")]
            found_session = any(c["name"] in SESSION_COOKIES for c in indeed_cookies)
            if found_session:
                print(f"[slot {slot}] Session detected at {(i + 1) * 10}s")
                break
            print(f"[slot {slot}]   {(i + 1) * 10}s elapsed — still waiting...")

        if found_session:
            out = os.path.join(COOKIES_DIR, f"account_{slot}.json")
            with open(out, "w") as f:
                json.dump(indeed_cookies, f, indent=2)
            print(f"[slot {slot}] ✅ Saved {len(indeed_cookies)} cookies → {out}")
            stop_profile(user_id)
            return True
        else:
            print(f"[slot {slot}] ❌ No session cookies — login not complete")
            stop_profile(user_id)
            return False


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

        # Skip slots that already have a cookie file
        existing = os.path.join(COOKIES_DIR, f"account_{slot}.json")
        if os.path.exists(existing):
            print(f"  slot {slot:2d}: ⏭  Already has cookies — skipping")
            ok += 1
            continue

        result  = await grab(slot, user_id, email, pw)
        if result:
            ok += 1
        print(f"[slot {slot}] Cooling down 10s before next profile...")
        await asyncio.sleep(10)

    print(f"\n✓ Done: {ok}/{len(profiles)} cookies saved")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", type=int, default=None,
                        help="Run only a specific account slot (1-10)")
    args = parser.parse_args()
    asyncio.run(main(only_slot=args.slot))
