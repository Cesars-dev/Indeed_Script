#!/usr/bin/env python3
"""
stress_test.py — Full apply run against a hardcoded job URL + profile.

Usage:
  python scripts/stress_test.py

No CSV, no N8N, no Supabase dedup — just raw apply_to_job().
Screenshots land in /tmp/apply_debug/<user_id>_<ts>/ every step.
Resume upload is skipped (no docx) so the script will navigate as far
as it can and return whatever status the state machine resolves.
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.nodriver_indeed import apply_to_job

# ── Config ─────────────────────────────────────────────────────────────────────
PROFILE_ID = "k19td50a"   # account 10 — oswaldin.lara@gmail.com

JOB_URL = (
    "https://www.indeed.com/viewjob?jk=dd00fe77c61a7833"
    "&q=paralegal&tk=1jhvuqcu1i966800&from=hp.jobsForYou"
    "&advn=2099254176450917&adid=449756692"
)

# Set to a local PDF/DOCX path to test resume upload, or None to skip
RESUME_PATH = None


# ── Run ────────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("STRESS TEST — full apply_to_job() run")
    print(f"Profile : {PROFILE_ID}")
    print(f"URL     : {JOB_URL[:80]}...")
    print(f"Resume  : {RESUME_PATH or '(none — upload step will be skipped)'}")
    print("=" * 60)

    debug_dir_hint = f"/tmp/apply_debug/{PROFILE_ID}_<ts>"
    print(f"\nScreenshots → {debug_dir_hint}/")
    print("Starting...\n")

    t0 = time.time()
    try:
        result = await apply_to_job(JOB_URL, RESUME_PATH, PROFILE_ID)
    except Exception as e:
        result = {"status": "error", "reason": str(e)}

    elapsed = time.time() - t0
    print("\n" + "=" * 60)
    print(f"RESULT  : {result['status']}")
    print(f"REASON  : {result.get('reason')}")
    print(f"ELAPSED : {elapsed:.1f}s")
    print("=" * 60)
    print(f"\nCheck screenshots: ls /tmp/apply_debug/")


if __name__ == "__main__":
    asyncio.run(main())
