import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def get_fresh_combinations(limit: int = 3):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/search_combinations",
        params={
            "active": "eq.true",
            "select": "*",
            "limit": limit,
            "order": "last_used.asc.nullsfirst",
        },
        headers=HEADERS,
        timeout=15
    )
    r.raise_for_status()
    combos = r.json()
    # Filter: last_used is null OR older than 7 days
    fresh = []
    now = datetime.now(timezone.utc)
    for c in combos:
        if c["last_used"] is None:
            fresh.append(c)
        else:
            from datetime import timedelta
            last = datetime.fromisoformat(c["last_used"].replace("Z", "+00:00"))
            if (now - last).days >= 7:
                fresh.append(c)
    return fresh


def mark_combination_used(combo_id: int):
    requests.patch(
        f"{SUPABASE_URL}/rest/v1/search_combinations",
        params={"id": f"eq.{combo_id}"},
        json={"last_used": datetime.now(timezone.utc).isoformat()},
        headers=HEADERS,
        timeout=15
    )




def log_execution(data: dict):
    """Insert one row into the executions table. Silently ignores errors."""
    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/executions",
            json=data,
            headers={**HEADERS, "Prefer": "return=minimal"},
            timeout=10,
        )
    except Exception as e:
        print(f"[supabase] log_execution error: {e}")
