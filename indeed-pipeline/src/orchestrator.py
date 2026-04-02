"""
Cron entry point: runs at 9 AM daily.
Queries Supabase for fresh search combinations → triggers N8N webhook.
Crontab: 0 9 * * * /root/indeed-pipeline/venv/bin/python /root/indeed-pipeline/src/orchestrator.py
"""
import os
import sys
import argparse
import requests
from dotenv import load_dotenv

load_dotenv()

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.supabase_client import get_fresh_combinations, mark_combination_used


def trigger_n8n(combos: list, dry_run: bool = False):
    payload = [
        {
            "position": combo["search_term"],
            "location": combo["state"],
            "country": "US",
            "maxItems": 100,
            "parseCompanyDetails": True,
            "saveOnlyUniqueItems": True,
            "followApplyRedirects": False,
            "combo_id": combo["id"],
        }
        for combo in combos
    ]
    if dry_run:
        print(f"[DRY RUN] Would POST to N8N: {payload}")
        return True
    r = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=30)
    print(f"N8N triggered with {len(combos)} combos: HTTP {r.status_code}")
    return r.status_code == 200


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print combos without triggering N8N")
    args = parser.parse_args()

    combos = get_fresh_combinations(limit=3)
    if not combos:
        print("No fresh combinations available today.")
        return

    print(f"Found {len(combos)} fresh combinations to process")
    success = trigger_n8n(combos, dry_run=args.dry_run)
    if success and not args.dry_run:
        for combo in combos:
            mark_combination_used(combo["id"])


if __name__ == "__main__":
    main()
