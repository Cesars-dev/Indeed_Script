#!/usr/bin/env python3
"""
Profile reset — deletes all 'indeed' group profiles from AdsPower,
creates 10 fresh ones with unassigned proxies from Supabase,
then updates Supabase adspower_profiles with the new user_ids.

Usage:
  python3.13 -u scripts/setup_profiles.py            # full reset
  python3.13 -u scripts/setup_profiles.py --dry-run  # preview only, no changes
"""
import argparse
import json
import os
import sys
import time
import requests
from dotenv import load_dotenv

# Load from indeed-pipeline/.env
_ENV = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=_ENV)

ADSPOWER_API     = os.getenv("ADSPOWER_BASE", "http://localhost:50325")
ADSPOWER_API_KEY = os.getenv("ADSPOWER_API_KEY")
INDEED_GROUP_ID  = os.getenv("ADSPOWER_GROUP_ID", "8765960")
SUPABASE_URL     = os.getenv("SUPABASE_URL")
SUPABASE_KEY     = os.getenv("SUPABASE_KEY")

for var, val in [("ADSPOWER_API_KEY", ADSPOWER_API_KEY), ("SUPABASE_URL", SUPABASE_URL), ("SUPABASE_KEY", SUPABASE_KEY)]:
    if not val:
        sys.exit(f"ERROR: {var} not set in .env")

SUPA_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


# ── AdsPower helpers ──────────────────────────────────────────────────────────

def adspower_get(path: str, params: dict = None) -> dict:
    p = {"api_key": ADSPOWER_API_KEY, **(params or {})}
    r = requests.get(f"{ADSPOWER_API}{path}", params=p, timeout=30)
    r.raise_for_status()
    return r.json()


def adspower_post(path: str, body: dict) -> dict:
    params = {"api_key": ADSPOWER_API_KEY}
    r = requests.post(f"{ADSPOWER_API}{path}", params=params, json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def list_indeed_profiles() -> list[dict]:
    data = adspower_get("/api/v1/user/list",
                        {"page": 1, "page_size": 100, "group_id": INDEED_GROUP_ID})
    return data.get("data", {}).get("list", [])


def delete_profiles(user_ids: list[str]) -> bool:
    data = adspower_post("/api/v1/user/delete", {"user_ids": user_ids})
    return data.get("code") == 0


def create_profile(slot: int, email: str, proxy: dict) -> str:
    """Create one AdsPower profile. Returns new user_id."""
    body = {
        "name": f"Indeed {slot:02d} — {email}",
        "group_id": INDEED_GROUP_ID,
        "domain_name": "indeed.com",
        "username": email,
        "user_proxy_config": {
            "proxy_soft": "other",
            "proxy_type": "http",
            "proxy_host": proxy["proxy_address"],
            "proxy_port": str(proxy["port"]),
            "proxy_user": proxy["username"],
            "proxy_password": proxy["password"],
        },
    }
    data = adspower_post("/api/v1/user/create", body)
    if data.get("code") != 0:
        raise RuntimeError(f"Create failed for slot {slot}: {data}")
    return data["data"]["id"]


# ── Supabase helpers ──────────────────────────────────────────────────────────

def fetch_unassigned_proxies(n: int) -> list[dict]:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/proxies",
        params={"assigned_to": "is.null", "select": "*",
                "order": "id.asc", "limit": n},
        headers=SUPA_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def fetch_supa_profiles() -> list[dict]:
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/adspower_profiles",
        params={"select": "id,account_slot,email,user_id", "order": "account_slot.asc"},
        headers=SUPA_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def update_supa_profile(row_id: int, new_user_id: str, proxy: dict):
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/adspower_profiles",
        params={"id": f"eq.{row_id}"},
        json={
            "user_id": new_user_id,
            "proxy_address": proxy["proxy_address"],
            "proxy_port": proxy["port"],
            "cookie_status": "pending",
            "cookie_file": None,
            "notes": None,
        },
        headers=SUPA_HEADERS,
        timeout=15,
    )


def mark_proxy_assigned(proxy_id: int, user_id: str):
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/proxies",
        params={"id": f"eq.{proxy_id}"},
        json={"assigned_to": user_id},
        headers=SUPA_HEADERS,
        timeout=15,
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main(dry_run: bool = False):
    tag = "[DRY RUN] " if dry_run else ""

    # 1. List current indeed profiles
    print("Fetching current AdsPower 'indeed' group profiles...")
    profiles = list_indeed_profiles()
    print(f"Found {len(profiles)} profiles to delete:")
    for p in profiles:
        print(f"  {p['user_id']}  {p.get('username','?')}")

    if not profiles:
        print("No profiles found — nothing to delete.")

    # 2. Fetch Supabase profiles (ordered by slot)
    print("\nFetching Supabase adspower_profiles...")
    supa_profiles = fetch_supa_profiles()
    n = len(supa_profiles)
    print(f"Found {n} Supabase profile rows (slots 1–{n})")

    # 3. Fetch fresh proxies
    print(f"\nFetching {n} unassigned proxies from Supabase...")
    proxies = fetch_unassigned_proxies(n)
    if len(proxies) < n:
        print(f"ERROR: only {len(proxies)} unassigned proxies available, need {n}")
        sys.exit(1)
    print(f"Got {len(proxies)} proxies — all US residential")

    # 4. Preview
    print("\n--- Plan ---")
    for i, sp in enumerate(supa_profiles):
        proxy = proxies[i]
        print(f"  slot {sp['account_slot']:2d}: {sp['email']:45} → proxy {proxy['proxy_address']}:{proxy['port']}")

    if dry_run:
        print("\n[DRY RUN] No changes made.")
        return

    # 5. Delete existing profiles
    if profiles:
        user_ids = [p["user_id"] for p in profiles]
        print(f"\nDeleting {len(user_ids)} profiles from AdsPower...")
        ok = delete_profiles(user_ids)
        if not ok:
            print("ERROR: delete failed — check AdsPower")
            sys.exit(1)
        print("Deleted.")
        time.sleep(3)

    # 6. Create new profiles + update Supabase
    print("\nCreating 10 fresh profiles...")
    results = []
    for i, sp in enumerate(supa_profiles):
        proxy = proxies[i]
        email = sp["email"]
        slot  = sp["account_slot"]
        print(f"  [{slot:2d}] Creating '{email}' with proxy {proxy['proxy_address']}:{proxy['port']}...", end=" ")
        new_uid = create_profile(slot, email, proxy)
        print(f"→ {new_uid}")

        update_supa_profile(sp["id"], new_uid, proxy)
        mark_proxy_assigned(proxy["id"], new_uid)
        results.append({"slot": slot, "user_id": new_uid, "email": email, "proxy": f"{proxy['proxy_address']}:{proxy['port']}"})
        time.sleep(1)

    # 7. Print summary
    print("\n✅ Done — new profile mapping:")
    print(f"{'slot':>4}  {'user_id':>12}  {'email':45}  proxy")
    print("-" * 100)
    for r in results:
        print(f"{r['slot']:>4}  {r['user_id']:>12}  {r['email']:45}  {r['proxy']}")

    print("\nNext step:")
    print("  venv_local/bin/python3.13 -u scripts/grab_cookies_manual.py")
    print("  (Manual login — DO NOT use export_cookies.py on fresh profiles)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only — no deletions or creations")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
