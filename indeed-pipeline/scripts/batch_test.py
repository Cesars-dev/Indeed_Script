"""
Batch apply test — alternates between profiles on failure, stops after MAX_FAILURES.

Usage:
  python3 scripts/batch_test.py

URLs hardcoded from APPLY_TESTS.md for debug session.
"""
import asyncio
import json
import os
import sys
import time
import uuid

import requests
from dotenv import load_dotenv

# Load .env from indeed-pipeline directory (override=True: wins over IDE-injected parent .env)
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path, override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.playwright_indeed import apply_to_job, _url_type  # noqa: E402
from src.smartapply.logger import log as sb_log             # noqa: E402
from src.gdrive_client import download_doc_as_pdf           # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────
def _load_active_profiles():
    """Pull active profile user_ids from Supabase — skip resting profiles."""
    # No profiles resting — all 5 active
    RESTING = set()
    # Dead proxy IPs no longer needed — all active profiles now have working proxies (swapped DOE iter 6)

    sb_url = os.getenv("SUPABASE_URL")
    sb_key = os.getenv("SUPABASE_KEY")
    if not sb_url or not sb_key:
        print("[batch] WARNING: SUPABASE env not set — using fallback profiles")
        return ["k1a2vu6e"]
    try:
        r = requests.get(
            f"{sb_url}/rest/v1/adspower_profiles",
            params={"select": "user_id,full_name,account_slot,proxy_address",
                    "status": "eq.active", "order": "account_slot"},
            headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}"},
            timeout=10,
        )
        r.raise_for_status()
        rows = r.json()
        good = []
        for row in rows:
            uid = row["user_id"]
            if uid in RESTING:
                print(f"  😴 Slot {row['account_slot']:2d} — {row.get('full_name','?')} ({uid}) — RESTING, skipping")
            else:
                print(f"  🟢 Slot {row['account_slot']:2d} — {row.get('full_name','?')} ({uid})")
                good.append(uid)
        if not good:
            print("[batch] ⚠️ No non-resting profiles!")
            return [row["user_id"] for row in rows]
        return good
    except Exception as e:
        print(f"[batch] WARNING: Failed to load profiles: {e}")
        return ["k1a2vu6e"]

PROFILES = _load_active_profiles()
RESUME_PATH   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resume_oswaldo.pdf")
MAX_FAILURES  = 10
SLEEP_BETWEEN = 15  # seconds between attempts (short for debug)
TRANSIENT_PATTERNS = ("Timeout", "Broken pipe", "JSONDecode", "HTTPConnectionPool", "TargetClosedError", "BrowserContext", "stone_walled", "CF challenge")

# ── Job URLs from Google Sheet ────────────────────────────────────────────────
SHEET_CSV = "https://docs.google.com/spreadsheets/d/1bR12LF7nCLANCz5hfRinIsbY9BXfCLF23ug8F_g_Nuw/export?format=csv&gid=0"

def _load_job_urls():
    """Pull apply URLs + cover letter doc URLs from the proposals Google Sheet."""
    import csv, io
    try:
        r = requests.get(SHEET_CSV, timeout=15)
        r.raise_for_status()
        reader = csv.DictReader(io.StringIO(r.text))
        jobs = []
        for row in reader:
            # Accept both old and new sheet column names
            url = (row.get("applyurl") or row.get("apply_url") or "").strip()
            doc_url = (row.get("Proposal URL") or row.get("google_doc_id") or "").strip()
            if url:
                jobs.append({"url": url, "doc_url": doc_url})
        print(f"[batch] Loaded {len(jobs)} job URLs from Google Sheet")
        return jobs
    except Exception as e:
        print(f"[batch] WARNING: Failed to load sheet: {e} — using fallback URLs")
        return [
            {"url": "https://www.indeed.com/viewjob?jk=d76e940c085fd63b", "doc_url": ""},
            {"url": "https://www.indeed.com/viewjob?jk=fdde4543ebe910de", "doc_url": ""},
        ]

_RAW_JOBS = _load_job_urls()


def _load_attempted_urls() -> set:
    """Pull permanently-done URLs from Supabase — transient failures stay retryable."""
    sb_url = os.getenv("SUPABASE_URL")
    sb_key = os.getenv("SUPABASE_KEY")
    if not sb_url or not sb_key:
        return set()
    try:
        r = requests.get(
            f"{sb_url}/rest/v1/test_run_logs",
            params={"select": "url,status,reason", "limit": 500},
            headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}"},
            timeout=10,
        )
        r.raise_for_status()
        done = set()
        for row in r.json():
            u = row.get("url", "")
            if not u:
                continue
            status = row.get("status", "")
            reason = row.get("reason", "")
            # Check if reason matches a transient/retryable pattern
            is_retryable = any(p in reason for p in TRANSIENT_PATTERNS)
            if is_retryable:
                pass  # leave retryable — don't add to done
            elif status in ("success", "skipped", "disqualified"):
                done.add(u)
            elif status == "failed":
                done.add(u)  # real failure — skip
            # else: transient failure — leave retryable
        retryable = len({row.get("url") for row in r.json() if row.get("url")} - done)
        print(f"[batch] Found {len(done)} done URLs in Supabase ({retryable} retryable)")
        return done
    except Exception as e:
        print(f"[batch] WARNING: Failed to load attempted URLs: {e}")
        return set()


_ATTEMPTED = _load_attempted_urls()
DEBUG_JOBS = [j for j in _RAW_JOBS if j["url"][:100] not in _ATTEMPTED]
print(f"[batch] After dedup: {len(DEBUG_JOBS)} URLs to try (skipped {len(_RAW_JOBS) - len(DEBUG_JOBS)} done)")


def _download_cover_letter(doc_url: str, job_id: str) -> str | None:
    """Download Google Doc as PDF via OAuth, return local path."""
    if not doc_url:
        return None
    out_dir = "/tmp/cover_letters"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{job_id}.pdf")
    if os.path.exists(out_path):
        return out_path  # cached
    try:
        download_doc_as_pdf(doc_url, out_path)
        return out_path
    except Exception as e:
        print(f"  ⚠️ Proposal download failed: {e} — using generic resume")
        return None

# ── Local log ─────────────────────────────────────────────────────────────────
LOG_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
RUN_ID   = str(uuid.uuid4())
LOG_FILE = os.path.join(LOG_DIR, f"batch_{int(time.time())}.jsonl")


def log(entry: dict):
    entry["ts"] = time.strftime("%H:%M:%S")
    line = json.dumps(entry)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    print(f"  [LOG] {line}")


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    # ── Pre-flight: restart AdsPower for clean CDP state ──────────────────
    adspower_base = os.getenv("ADSPOWER_BASE", "http://127.0.0.1:30025")
    adspower_key  = os.getenv("ADSPOWER_API_KEY", "")
    print("[batch] 🔄 Restarting AdsPower for clean CDP state...")
    os.system("sudo systemctl stop adspower 2>/dev/null; sleep 2; "
              "sudo rm -f /root/.config/adspower_global/Singleton* 2>/dev/null; "
              "sudo systemctl start adspower 2>/dev/null")
    print("[batch] ⏳ Waiting 60s for AdsPower to stabilize...")
    await asyncio.sleep(60)
    # Verify AdsPower is responding
    for check in range(6):
        try:
            r = requests.get(
                f"{adspower_base}/api/v1/user/list",
                params={"api_key": adspower_key, "page": 1, "page_size": 1},
                timeout=5,
            )
            if r.status_code == 200 and r.json().get("code") == 0:
                print(f"[batch] ✅ AdsPower is up and responding")
                break
        except Exception:
            pass
        if check < 5:
            print(f"[batch] ⚠️ AdsPower not ready (attempt {check+1}/6) — waiting 15s...")
            await asyncio.sleep(15)
        else:
            print(f"[batch] ❌ AdsPower failed to start — aborting")
            return

    generic_resume = RESUME_PATH if os.path.exists(RESUME_PATH) else None
    print(f"[batch] Generic resume: {generic_resume or 'MISSING'}")
    print(f"[batch] Profiles: {PROFILES}")
    print(f"[batch] URLs: {len(DEBUG_JOBS)}  |  max_failures: {MAX_FAILURES}  |  sleep: {SLEEP_BETWEEN}s")
    print(f"[batch] Log: {LOG_FILE}\n")

    total_failures = 0
    profile_idx    = 0
    attempt        = 0

    for job in DEBUG_JOBS:
        url = job["url"]
        if total_failures >= MAX_FAILURES:
            print(f"\n[batch] ⛔ Reached {MAX_FAILURES} failures — stopping.")
            break

        success = False
        url_attempts = 0

        while not success:
            if total_failures >= MAX_FAILURES:
                print(f"\n[batch] ⛔ Reached {MAX_FAILURES} total failures — stopping.")
                break

            profile_id = PROFILES[profile_idx % len(PROFILES)]
            attempt   += 1
            url_attempts += 1
            kind       = _url_type(url)
            short_url  = url[:80] + "..." if len(url) > 80 else url

            print(f"\n{'='*70}")
            print(f"[batch] Attempt {attempt} | Profile: {profile_id} | URL: {short_url}")
            print(f"[batch] failures so far: {total_failures}/{MAX_FAILURES}")
            print(f"{'='*70}")

            t0 = time.time()
            # Download per-job cover letter (or fall back to generic)
            jk = url.split("jk=")[-1][:20] if "jk=" in url else "unknown"
            cover = _download_cover_letter(job.get("doc_url", ""), jk) or generic_resume
            try:
                result = await apply_to_job(url, cover, profile_id)
            except Exception as e:
                result = {"status": "failed", "reason": str(e)}

            elapsed = time.time() - t0
            entry = {
                "attempt":    attempt,
                "profile_id": profile_id,
                "url":        url[:100],
                "url_type":   kind,
                "elapsed_s":  round(elapsed, 1),
                **result,
            }
            log(entry)
            sb_log("test_run_logs", {
                "run_id":     RUN_ID,
                "job_num":    attempt,
                "url":        url[:500],
                "url_type":   kind,
                "status":     result["status"],
                "reason":     result.get("reason", "")[:500],
                "elapsed_s":  round(elapsed, 1),
                "profile_id": profile_id,
            })

            status = result["status"]
            reason = result.get("reason", "")
            print(f"\n  ★ [{profile_id}] {status} — {reason}")

            if status in ("success", "skipped", "disqualified"):
                if "stone_walled" in reason:
                    # Profile is walled — rotate to next profile, retry same URL
                    profile_idx += 1
                    print(f"  🧱 Profile stonewalled — rotating to {PROFILES[profile_idx % len(PROFILES)]}")
                    continue  # retry same URL with new profile
                success = True
                print(f"  ✅ Done with this URL ({status}).")
                if status == "success":
                    try:
                        tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
                        tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")
                        if tg_token and tg_chat:
                            cover_name = os.path.basename(cover) if cover else "none"
                            requests.post(
                                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                                json={"chat_id": int(tg_chat), "text": f"✅ APPLICATION SUBMITTED\nProfile: {profile_id}\nURL: {url[:80]}\nCover: {cover_name}\nTime: {round(elapsed)}s"},
                                timeout=5,
                            )
                    except Exception:
                        pass
            elif status == "failed" and any(p in reason for p in TRANSIENT_PATTERNS):
                # Infrastructure hiccup — don't count toward failure budget
                profile_idx += 1
                print(f"  ⚡ Transient error — not counting toward failures. Rotating profile.")
                if total_failures < MAX_FAILURES:
                    await asyncio.sleep(SLEEP_BETWEEN)
            elif url_attempts >= 2:
                # Don't hammer the same URL — move on after 2 tries
                total_failures += 1
                profile_idx   += 1
                print(f"  ⏭️  Max retries for this URL ({url_attempts}) — moving on")
                break
            else:
                total_failures += 1
                profile_idx   += 1  # rotate to next profile
                print(f"  ❌ Failed ({total_failures}/{MAX_FAILURES}) — rotating to {PROFILES[profile_idx % len(PROFILES)]}")
                if total_failures < MAX_FAILURES:
                    print(f"  Sleeping {SLEEP_BETWEEN}s...")
                    await asyncio.sleep(SLEEP_BETWEEN)

    print(f"\n{'='*70}")
    print(f"[batch] DONE | attempts: {attempt} | failures: {total_failures} | run_id={RUN_ID}")
    print(f"[batch] Full log: {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
