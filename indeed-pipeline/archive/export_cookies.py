#!/usr/bin/env python3
"""
Run this on your Mac with AdsPower open.
Launches each 'indeed' group profile, logs into Indeed via Google,
exports session cookies → config/cookies/account_N.json

Usage:
  python scripts/export_cookies.py

Then upload to VPS:
  scp -r config/cookies/ root@45.55.90.156:/root/indeed-pipeline/config/
"""
import asyncio
import json
import os
import requests
from playwright.async_api import async_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADSPOWER_API = "http://local.adspower.net:50325"
GROUP_ID = "8765960"  # 'indeed' group
COOKIES_DIR = os.path.join(BASE_DIR, "config", "cookies")
ACCOUNTS_FILE = os.path.join(BASE_DIR, "config", "accounts.json")

os.makedirs(COOKIES_DIR, exist_ok=True)


def get_profiles():
    r = requests.get(f"{ADSPOWER_API}/api/v1/user/list",
                     params={"page": 1, "page_size": 100, "group_id": GROUP_ID})
    return r.json()["data"]["list"]


def start_profile(user_id: str):
    import time, random
    # Stop first to clear any stale browser instance
    requests.get(f"{ADSPOWER_API}/api/v1/browser/stop", params={"user_id": user_id})
    time.sleep(random.uniform(5, 8))
    r = requests.get(f"{ADSPOWER_API}/api/v1/browser/start",
                     params={"user_id": user_id, "headless": "0"})
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Failed to start profile {user_id}: {data}")
    return data["data"]


def stop_profile(user_id: str):
    requests.get(f"{ADSPOWER_API}/api/v1/browser/stop", params={"user_id": user_id})


def load_accounts():
    with open(ACCOUNTS_FILE) as f:
        return json.load(f)


async def login_and_export(user_id: str, email: str, password: str, account_num: int):
    print(f"\n[{account_num}] Starting profile {user_id} for {email}...")
    browser_data = start_profile(user_id)
    ws_url = browser_data.get("ws", {}).get("puppeteer")

    if not ws_url:
        print(f"[{account_num}] No WebSocket URL — skipping")
        return False

    print(f"[{account_num}] Connecting via CDP: {ws_url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(ws_url)
            await asyncio.sleep(5)  # Let browser fully stabilize after CDP connect
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            pages = context.pages
            page = pages[0] if pages else await context.new_page()

            await page.goto("https://www.indeed.com", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Check if already logged in
            content = await page.content()
            if "Sign in" not in content:
                print(f"[{account_num}] Already logged in!")
            else:
                # Click Sign in
                try:
                    await page.click("a[href*='account/login'], button[data-gnav-element-name='SignIn']", timeout=5000)
                    await asyncio.sleep(2)
                except Exception:
                    pass

                # Click Google sign-in — may open a popup
                try:
                    await page.wait_for_selector("button[data-tn-element='googleButton'], [data-testid='google-login-button']", timeout=5000)
                    async with context.expect_page() as popup_info:
                        await page.click("button[data-tn-element='googleButton'], [data-testid='google-login-button']")
                    google_page = await popup_info.value
                    await google_page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(2)
                except Exception:
                    # No popup — Google login might be inline
                    google_page = page

                # Enter email
                try:
                    await google_page.wait_for_selector("input[type='email']", timeout=8000)
                    await google_page.type("input[type='email']", email, delay=80)
                    await asyncio.sleep(1)
                    await google_page.keyboard.press("Enter")
                    await asyncio.sleep(3)
                except Exception:
                    pass

                # Enter password
                try:
                    await google_page.wait_for_selector("input[type='password']", timeout=8000)
                    await google_page.type("input[type='password']", password, delay=80)
                    await asyncio.sleep(1)
                    await google_page.keyboard.press("Enter")
                    await asyncio.sleep(4)
                except Exception:
                    pass

            # Wait for Cloudflare + login to settle
            print(f"[{account_num}] Waiting 60s for Cloudflare/login to settle...")
            await asyncio.sleep(60)

            # Re-fetch context/cookies after navigation (Cloudflare may have shifted context)
            try:
                all_contexts = browser.contexts
                all_cookies = []
                for ctx in all_contexts:
                    try:
                        cookies = await ctx.cookies()
                        all_cookies.extend(cookies)
                    except Exception:
                        pass
            except Exception as e:
                print(f"[{account_num}] Could not get cookies: {e}")
                return False

            indeed_cookies = [c for c in all_cookies if "indeed.com" in c.get("domain", "")]

            if not indeed_cookies:
                print(f"[{account_num}] No Indeed cookies — login failed")
                return False

            # Verify session cookie present
            session_names = {"CTK", "indeed_sess", "INDEED_CSRF_TOKEN", "LC"}
            found_session = any(c.get("name") in session_names for c in indeed_cookies)
            if not found_session:
                print(f"[{account_num}] Only tracking cookies found, no session — login incomplete")
                return False

            print(f"[{account_num}] Session cookie confirmed ✓")

            output = os.path.join(COOKIES_DIR, f"account_{account_num}.json")
            with open(output, "w") as f:
                json.dump(indeed_cookies, f, indent=2)
            print(f"[{account_num}] Saved {len(indeed_cookies)} cookies → {output}")
            return True

    except Exception as e:
        print(f"[{account_num}] Error: {e}")
        return False
    finally:
        stop_profile(user_id)
        await asyncio.sleep(3)


async def main():
    profiles = get_profiles()
    accounts = load_accounts()

    if not profiles:
        print("No profiles found in 'indeed' group.")
        return

    print(f"Found {len(profiles)} profiles, {len(accounts)} accounts")

    success_count = 0
    for i, (profile, account) in enumerate(zip(profiles, accounts)):
        ok = await login_and_export(
            user_id=profile["user_id"],
            email=account["email"],
            password=account["password"],
            account_num=i + 1
        )
        if ok:
            success_count += 1

    print(f"\n✓ Done: {success_count}/{len(profiles)} profiles exported")
    print(f"\nUpload to VPS:")
    print(f"  scp -i ~/.ssh/id_rsa -r config/cookies/ root@45.55.90.156:/root/indeed-pipeline/config/")


if __name__ == "__main__":
    asyncio.run(main())
