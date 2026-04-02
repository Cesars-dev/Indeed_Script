"""
Test runner — applies to jobs via Mac AdsPower GUI (port 50325, debug port 52018).
Saves DOM + screenshots per step for analysis.
"""
import asyncio
import json
import os
import sys
import time

# Override env BEFORE importing pipeline modules
os.environ["ADSPOWER_BASE"] = "http://local.adspower.net:50325"
os.environ["RUN_MODE"] = "local"

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.playwright_indeed import (
    apply_to_job, _start_profile, _stop_profile,
    _url_type, ADSPOWER_API_KEY, DEBUG_DIR_BASE,
)

PROFILE_ID = "k1a2vupc"
FIXED_DEBUG_PORT = 52018
RESUME_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resume_oswaldo.pdf")
SLEEP_BETWEEN = 30
DOM_DIR = "/tmp/dom_dumps"

URLS = [
    "https://www.indeed.com/viewjob?jk=9868e93b0d5f14d1&tk=1jjj6gtetg04g803&from=hp.jobsForYou&advn=8666959841414475&adid=457840063&ad=-6NYlbfkN0Bx08vEc3Hd0Xw5SJRs4Q_CTybyg0hJGdWI8FO9IwAWqJRjVsJk4UYkduEWGDxjTVicxaxQV2bJ4191Sk7zTuhOlG8en7FZQlF4HH3UBIz3OXcZvo0-kNb0UAzcADHZSnsP_tsvEY2FZkchXb0uELH25-jq4zqiNShj8bMSsH6xgaePt0sbVE6sGNOV4lhySSHk602Tcv_gPkrZox1LfXf0hUyW5i1ThwKsBbeT54IlRxr_3Wsl4Q77uGY-s9jifi9znxN96mV5sydB-YjRzSXclznUQE4kD6o43LxZODZZGuPGdB69u9OeHgdfFsEVSNZ-0nwmIK8dIKoNi8Kkl85YnbiNj6wB63eAqitP2diuptV2PBuqfZBAQcjsUtHMNqSMyMfZ6IWP-4aIMOHX7jlLjLXR40AaULSM4vRQSZys9HTnjWPvMi9xrUeL8c7u_JuEbcPvRc8qZEQh3NHmhoiqEddD7i59KHRAZbfWEfZvaAdq_PMGs7YyoqouAUMcA8dbE-WSsc6YCEfSfxUEHwSlvJmyBLkZpNM5nu2mYrOmeVq9I8wmxVNHVSMXTmy1PO82AoFgIs9JwoUCrwoArw_0Xfaezm-1QEjEebPT7uGZ7w%3D%3D&pub=4a1b367933fd867b19b072952f68dceb&camk=UoKtGZLa3XLuYkD_K1mddA%3D%3D&xkcb=SoDS6_M3mzFMahAHxz0ObzkdCdPP&xpse=SoA66_I3mzFLNIROyJ0ObzkdCdPP&xfps=1022982f-f275-47f4-a3d2-c467764ca4de&vjs=3",
    "https://www.indeed.com/viewjob?jk=b5323afd8d319c8e&q=receptionist&tk=1jjj6gtetg04g803&from=hp.jobsForYou&advn=2707748914787695&adid=458557576&ad=-6NYlbfkN0AcBG3TI2wKN63db2uUCEzeaT_rd1PiE7liOburrlofocy__hmZwXmX-Xq9JP6aCNH_JihkFCgG-fYiyqpOIl500gfm_q1RUpxGO_YEOIyPeQvpTmKU0nm6FjHjSGjDv1bBEnF33Bow_bVZme-CxQyHRXJ6mGNPGHz5id0N8Z_wmJ3bahiDoXNoB8yMSBvlQKqUy9YyIaXLy7F77H-sjI2ndiRl57emTnckLdeiTqtx73dG2j9P69GK543aRVeghLYT0h9OPL6xm0qWC_tbhOLmQBG1Jsp_FxvgKRHH7dJm4EKwWjzw6mIGueOsnimhbbmangpDrB-MHXyfBXFZ0pF4ecMEReBV267-V6uIDQSluIobSrrPYekMkkH54HYhrgqJeBliN6F2miZhnEZzuBWI4FP2Mbp_iWw-BBLsTwgxxqz-057SENH_kSQnRslwg0Lw8vyHlzDnIGj3_iWXSo2F9JxvyJPgSf38O6w622BQu-j1Rkf7XW015vwI5XYxs_2pDDBa84yfslqc6zoXLFBUwsvX3squlYh2FKsThZhY1IMAitaJc2OoTF5hiQWg4WWNWRZq-Xogul9vgcZX8zZceshSho_VMYLILYF6LMuV5Q%3D%3D&pub=4a1b367933fd867b19b072952f68dceb&camk=UoKtGZLa3XKmAXc_kCasyA%3D%3D&xkcb=SoCm6_M3mzFMahAHxz0CbzkdCdPP&xpse=SoC66_I3mzFK4GQUt50PbzkdCdPP&xfps=f9ac177f-14b5-4483-89e2-4fea0b653967&vjs=3",
]


async def main():
    os.makedirs(DOM_DIR, exist_ok=True)
    resume = RESUME_PATH if os.path.exists(RESUME_PATH) else None

    print(f"{'='*70}")
    print(f"  TEST RUN — Mac AdsPower GUI")
    print(f"  Profile:    {PROFILE_ID}")
    print(f"  Debug port: {FIXED_DEBUG_PORT} (tunneled)")
    print(f"  Resume:     {resume or 'NONE'}")
    print(f"  URLs:       {len(URLS)}")
    print(f"  DOM dumps:  {DOM_DIR}/")
    print(f"{'='*70}\n")

    results = []
    for i, url in enumerate(URLS):
        kind = _url_type(url)
        jk = "unknown"
        if "jk=" in url:
            jk = url.split("jk=")[1].split("&")[0]

        print(f"\n{'='*70}")
        print(f"  JOB {i+1}/{len(URLS)} [{kind}] jk={jk}")
        print(f"{'='*70}")

        t0 = time.time()
        try:
            result = await apply_to_job(url, resume, PROFILE_ID)
        except Exception as e:
            result = {"status": "error", "reason": str(e)}
            import traceback
            traceback.print_exc()

        elapsed = round(time.time() - t0, 1)
        result["elapsed_s"] = elapsed
        result["job_num"] = i + 1
        result["jk"] = jk
        results.append(result)

        print(f"\n  ★ Result: {result['status']} — {result.get('reason', '')}")
        print(f"  ★ Elapsed: {elapsed}s")

        # Save DOM snapshot
        dom_file = os.path.join(DOM_DIR, f"job{i+1}_{jk}_{result['status']}.html")
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{FIXED_DEBUG_PORT}")
                ctx = browser.contexts[0]
                if len(ctx.pages) > 1:
                    page = ctx.pages[1]
                    html = await page.content()
                    with open(dom_file, "w") as f:
                        f.write(html)
                    print(f"  📄 DOM saved: {dom_file}")
        except Exception as e:
            print(f"  ⚠️ DOM save failed: {e}")

        if i < len(URLS) - 1:
            print(f"\n  ⏳ Sleeping {SLEEP_BETWEEN}s before next job...")
            await asyncio.sleep(SLEEP_BETWEEN)

    # Summary
    print(f"\n{'='*70}")
    print(f"  SUMMARY — {len(URLS)} jobs")
    print(f"{'='*70}")
    for r in results:
        print(f"  Job {r['job_num']} (jk={r['jk']}): {r['status']:12s} | {r.get('reason','')[:60]} | {r['elapsed_s']}s")
    print(f"\n  DOM dumps: {DOM_DIR}/")
    print(f"  Screenshots: {DEBUG_DIR_BASE}/")


if __name__ == "__main__":
    asyncio.run(main())
