#!/usr/bin/env python3
"""
inject_firefox_cookies.py — Extract Google + Indeed cookies from Firefox and
inject them into an AdsPower profile via the local API.

Usage:
  python scripts/inject_firefox_cookies.py --user-id k19td4vp

Steps:
  1. Close Firefox (or the script copies the DB to /tmp to avoid lock errors)
  2. Run this script with the AdsPower profile user_id
  3. Open that AdsPower profile — it will be logged in to Google + Indeed

Notes:
  - Log into Gmail AND indeed.com in Firefox first, then run this script
  - Firefox must be closed OR the copy-workaround handles the lock
  - Repeat for each profile (log out of Google in Firefox first, then log in
    as the next account before running again)
"""
import argparse
import glob
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time

import requests
from dotenv import load_dotenv

# Load from indeed-pipeline/.env (works whether run from project root or scripts/)
_ENV = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=_ENV)

ADSPOWER_BASE    = os.getenv("ADSPOWER_BASE", "http://localhost:50325")
ADSPOWER_API_KEY = os.getenv("ADSPOWER_API_KEY")
if not ADSPOWER_API_KEY:
    sys.exit("ERROR: ADSPOWER_API_KEY not set in .env")

# Domains we want cookies for
TARGET_DOMAINS = [
    ".google.com",
    "google.com",
    ".accounts.google.com",
    "accounts.google.com",
    ".indeed.com",
    "indeed.com",
    ".smartapply.indeed.com",
    "smartapply.indeed.com",
    "secure.indeed.com",
    ".secure.indeed.com",
]

# sameSite mapping: Firefox integer → string
SAMESITE_MAP = {0: "None", 1: "Lax", 2: "Strict"}


def find_firefox_cookies_db() -> str:
    """Find the most recently used Firefox profile's cookies.sqlite on macOS."""
    base = os.path.expanduser("~/Library/Application Support/Firefox/Profiles")
    if not os.path.isdir(base):
        raise FileNotFoundError(f"Firefox profiles not found at: {base}")

    # Find all cookies.sqlite files, pick the most recently modified
    candidates = glob.glob(os.path.join(base, "*", "cookies.sqlite"))
    if not candidates:
        raise FileNotFoundError("No cookies.sqlite found in any Firefox profile")

    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]


def read_cookies(db_path: str) -> list[dict]:
    """Read cookies from Firefox SQLite DB, filtered to target domains."""
    # Copy to /tmp — Firefox may have a lock on the original
    tmp = tempfile.mktemp(suffix=".sqlite")
    shutil.copy2(db_path, tmp)

    try:
        conn = sqlite3.connect(tmp)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # moz_cookies schema: name, value, host, path, expiry, isSecure, isHttpOnly, sameSite
        cur.execute("""
            SELECT name, value, host, path, expiry, isSecure, isHttpOnly, sameSite
            FROM moz_cookies
            WHERE host IN ({})
            ORDER BY host, name
        """.format(",".join("?" * len(TARGET_DOMAINS))), TARGET_DOMAINS)

        rows = cur.fetchall()
        conn.close()
    finally:
        os.unlink(tmp)

    cookies = []
    for row in rows:
        cookies.append({
            "name":     row["name"],
            "value":    row["value"],
            "domain":   row["host"],
            "path":     row["path"],
            "expires":  row["expiry"],
            "httpOnly": bool(row["isHttpOnly"]),
            "secure":   bool(row["isSecure"]),
            "sameSite": SAMESITE_MAP.get(row["sameSite"], "None"),
        })

    return cookies


def inject_cookies(user_id: str, cookies: list[dict]) -> None:
    """Push cookies into AdsPower profile via the update API."""
    cookie_json = json.dumps(cookies)

    resp = requests.post(
        f"{ADSPOWER_BASE}/api/v1/user/update",
        params={"api_key": ADSPOWER_API_KEY},
        json={
            "user_id": user_id,
            "user_cookie": cookie_json,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"AdsPower update failed: {data}")


def main():
    parser = argparse.ArgumentParser(description="Inject Firefox cookies into AdsPower profile")
    parser.add_argument("--user-id", required=True, help="AdsPower profile user_id (e.g. k19td4vp)")
    parser.add_argument("--firefox-db", help="Path to Firefox cookies.sqlite (auto-detected if omitted)")
    parser.add_argument("--dry-run", action="store_true", help="Print cookies only, don't inject")
    args = parser.parse_args()

    # Find Firefox cookies DB
    db_path = args.firefox_db or find_firefox_cookies_db()
    print(f"Firefox DB : {db_path}")

    # Read cookies
    cookies = read_cookies(db_path)
    if not cookies:
        print("ERROR: No matching cookies found.")
        print("Make sure you're logged into Gmail AND indeed.com in Firefox first.")
        sys.exit(1)

    # Group for display
    by_domain: dict[str, list] = {}
    for c in cookies:
        by_domain.setdefault(c["domain"], []).append(c["name"])

    print(f"\nFound {len(cookies)} cookies across {len(by_domain)} domains:")
    for domain, names in sorted(by_domain.items()):
        print(f"  {domain}: {', '.join(names[:8])}{'...' if len(names) > 8 else ''}")

    if args.dry_run:
        print("\n[dry-run] Not injecting.")
        return

    # Inject
    print(f"\nInjecting into AdsPower profile: {args.user_id} ...")
    inject_cookies(args.user_id, cookies)
    print("✓ Done. Open the profile in AdsPower — it should be logged in.")
    print("  Verify by navigating to indeed.com inside the profile browser.")


if __name__ == "__main__":
    main()
