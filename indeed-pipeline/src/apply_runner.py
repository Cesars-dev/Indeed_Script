"""
Main apply loop — reads jobs from Google Sheet, downloads proposals via OAuth,
dedupes via Supabase, applies on Indeed with per-job proposal PDF.

Usage:
  python src/apply_runner.py                          # uses default Google Sheet
  python src/apply_runner.py <csv_url>                # override sheet URL
"""
import asyncio
import csv
import io
import os
import random
import sys

import requests
from dotenv import load_dotenv

# Load .env from indeed-pipeline directory (override=True: wins over IDE-injected parent .env)
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path, override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.gdrive_client import download_doc_as_pdf
from src.playwright_indeed import apply_to_job
from src.smartapply.logger import log as sb_log

# ── Default Google Sheet ──────────────────────────────────────────────────────
DEFAULT_SHEET_CSV = "https://docs.google.com/spreadsheets/d/1bR12LF7nCLANCz5hfRinIsbY9BXfCLF23ug8F_g_Nuw/export?format=csv&gid=0"

# 5 verified profiles — active sessions, cookies, alive residential proxies
PROFILE_IDS = [
    "k1a2vu6e",  # slot 9  - Abraham Ibarra
    "k19td50a",  # slot 10 - Oswaldo Lara
    "k1a2vul9",  # slot 11 - Alejandra Lizzete
    "k1a2vun1",  # slot 12 - Angel Ivan Lopez
    "k1a2vupc",  # slot 19 - M. Conchita
]

MAX_APPLIES_PER_ACCOUNT = 5  # cap per cycle to avoid flagging
RESUME_FALLBACK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resume_oswaldo.pdf")


def load_csv(url: str):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))


def _is_job_applied(job_id: str) -> bool:
    """Check if we already applied to this job via Supabase executions table."""
    sb_url = os.getenv("SUPABASE_URL")
    sb_key = os.getenv("SUPABASE_KEY")
    if not sb_url or not sb_key:
        return False
    try:
        r = requests.get(
            f"{sb_url}/rest/v1/executions",
            params={"select": "id", "job_id": f"eq.{job_id}", "status": "eq.success", "limit": 1},
            headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}"},
            timeout=10,
        )
        r.raise_for_status()
        return len(r.json()) > 0
    except Exception:
        return False


def _download_proposal(doc_url: str, job_id: str) -> str | None:
    """Download Google Doc proposal as PDF via OAuth. Returns local path or None."""
    if not doc_url:
        return None
    out_dir = "/tmp/proposals"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{job_id}.pdf")
    if os.path.exists(out_path):
        return out_path  # cached from previous attempt
    try:
        download_doc_as_pdf(doc_url, out_path)
        return out_path
    except Exception as e:
        print(f"  ⚠️ Proposal download failed: {e}")
        return None


async def process_job(job: dict, index: int, applied_counter: int, account_apply_counts: dict) -> int:
    # Accept both old and new sheet column names
    job_id = job.get("JobId") or job.get("job_id") or job.get("jobId") or job.get("id")
    apply_url = job.get("applyurl") or job.get("apply_url") or job.get("applyUrl") or job.get("url")
    doc_url = job.get("Proposal URL") or job.get("google_doc_id") or job.get("docId") or job.get("doc_id")
    company = job.get("Company name") or job.get("company") or ""
    title = job.get("Position") or job.get("title") or ""
    search_term = job.get("Search Term") or job.get("search_term") or ""
    state = job.get("state", "")

    if not job_id or not apply_url:
        print(f"[{index}] Skipping — missing job_id or url: {job}")
        return 0

    if not doc_url:
        print(f"[{index}] Skipping {job_id} — no proposal URL (proposal is required)")
        return 0

    if _is_job_applied(job_id):
        print(f"[{index}] {job_id} already applied, skipping")
        return 0

    # Download proposal as PDF via OAuth
    proposal_path = _download_proposal(doc_url, job_id)
    if not proposal_path:
        print(f"[{index}] Skipping {job_id} — proposal download failed")
        sb_log("executions", {
            "job_id": job_id, "status": "failed", "reason": "Proposal download failed",
            "company": company, "title": title, "state": state, "search_term": search_term
        })
        return 0

    # Rotate by actual apply count, skip accounts at their limit
    account_idx = applied_counter % len(PROFILE_IDS)
    for _ in range(len(PROFILE_IDS)):
        if account_apply_counts.get(account_idx, 0) < MAX_APPLIES_PER_ACCOUNT:
            break
        account_idx = (account_idx + 1) % len(PROFILE_IDS)
    else:
        print(f"[{index}] All accounts at max apply limit — stopping run")
        return -1

    user_id = PROFILE_IDS[account_idx]
    account_apply_counts[account_idx] = account_apply_counts.get(account_idx, 0) + 1

    print(f"[{index}] Applying: {title} @ {company} | account_{account_idx + 1} (profile: {user_id})")

    try:
        result = await apply_to_job(apply_url, proposal_path, user_id)
    except Exception as e:
        result = {"status": "failed", "reason": str(e)}

    sb_log("executions", {
        "job_id": job_id,
        "status": result["status"],
        "reason": result.get("reason", "")[:500],
        "account_id": str(account_idx + 1),
        "profile_id": user_id,
        "company": company,
        "title": title,
        "state": state,
        "search_term": search_term,
    })
    print(f"[{index}] {job_id}: {result['status']} — {result.get('reason')}")

    # Cleanup proposal PDF
    if proposal_path and os.path.exists(proposal_path):
        os.remove(proposal_path)

    delay = random.uniform(12, 45)
    print(f"[{index}] Waiting {delay:.1f}s before next job...")
    await asyncio.sleep(delay)
    return 1


async def main(csv_url: str):
    cycle = 0
    attempted_job_ids = set()  # Avoid re-applying to "failed" bugged jobs in the same run

    while True:
        cycle += 1
        print(f"\n{'='*70}")
        print(f"[runner] ═══ CYCLE {cycle} ═══  Loading jobs from: {csv_url}")
        print(f"{'='*70}")
        jobs = load_csv(csv_url)
        print(f"[runner] Total jobs in sheet: {len(jobs)}")

        applied_counter = 0
        account_apply_counts = {}
        exhausted = False
        
        for i, job in enumerate(jobs):
            job_id = job.get("JobId", "").strip()
            if not job_id or job_id in attempted_job_ids:
                continue

            delta = await process_job(job, i, applied_counter, account_apply_counts)
            if delta == -1:  # all accounts exhausted signal
                exhausted = True
                break
                
            attempted_job_ids.add(job_id)
            applied_counter += delta

        print(f"\n[runner] Cycle {cycle} done — applied to {applied_counter} jobs this round.")

        if not exhausted:
            print(f"[runner] ✅ All jobs in sheet completely processed. Shutting down pipeline.")
            break

        print(f"[runner] 💤 Sleeping 1 hour before next cycle...")
        await asyncio.sleep(3600)


if __name__ == "__main__":
    csv_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SHEET_CSV
    asyncio.run(main(csv_url))
