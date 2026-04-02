#!/usr/bin/env python3
"""Rerun cookie export for specific failed accounts only."""
import asyncio, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from main script
exec(open(os.path.join(os.path.dirname(__file__), "export_cookies.py")).read().split("if __name__")[0])

# Failed: account numbers and their profile/account pairs from the main run
# Profiles list from AdsPower is returned newest-first, so index 0 = account 10, index 5 = account 5, etc.
RERUN = [
    # (account_num, profile_user_id, email, password)
    # Fresh profiles created 2026-02-19 with new proxies (184.174.43.73:6613, 38.154.205.248:5516)
    (10, "k19t64wj", "oswaldin.lara@gmail.com",             "Simonala123"),
]

async def main():
    import random
    success = 0
    for account_num, user_id, email, password in RERUN:
        ok = await login_and_export(user_id, email, password, account_num)
        if ok:
            success += 1
        delay = random.uniform(15, 25)
        print(f"  Cooling down {delay:.0f}s before next account...")
        await asyncio.sleep(delay)
    print(f"\n✓ Done: {success}/{len(RERUN)} recovered")
    if success > 0:
        print("Upload to VPS:")
        print("  scp -i ~/.ssh/id_rsa -r config/cookies/ root@45.55.90.156:/root/indeed-pipeline/config/")

if __name__ == "__main__":
    asyncio.run(main())
