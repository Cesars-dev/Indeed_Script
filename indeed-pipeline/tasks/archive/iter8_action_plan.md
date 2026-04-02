# Surgeon Action Plan — Iteration 8

## Change 1: Smart Dedup (`batch_test.py` lines 93-116)

### Current
```python
r = requests.get(f"{sb_url}/rest/v1/test_run_logs",
    params={"select": "url", "limit": 500}, ...)
attempted = {row["url"] for row in r.json() if row.get("url")}
```

### Proposed
```python
TRANSIENT_PATTERNS = ("Timeout", "Broken pipe", "JSONDecode", "HTTPConnectionPool", "TargetClosedError", "BrowserContext")

r = requests.get(f"{sb_url}/rest/v1/test_run_logs",
    params={"select": "url,status,reason", "limit": 500}, ...)
done = set()
for row in r.json():
    u = row.get("url", "")
    if not u:
        continue
    status = row.get("status", "")
    reason = row.get("reason", "")
    if status in ("success", "skipped", "disqualified"):
        done.add(u)
    elif status == "failed" and not any(p in reason for p in TRANSIENT_PATTERNS):
        done.add(u)  # real failure — skip
    # else: transient failure — leave retryable
attempted = done
```

---

## Change 2: JSON Parse Fallback (`gemini_fallback.py` lines 131-136)

### Current
```python
raw = resp.text.strip()
if raw.startswith("```"):
    raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
return json.loads(raw)
```

### Proposed
```python
raw = resp.text.strip()
if raw.startswith("```"):
    raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
try:
    return json.loads(raw)
except json.JSONDecodeError:
    import re
    m = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw)
    if m:
        return json.loads(m.group())
    print(f"  ⚠️ Gemini returned unparseable JSON: {raw[:100]}")
    return {"action": "scroll", "target": "", "reason": "bad JSON — scrolling to retry"}
```

---

## Change 3: Same-URL Bail-out (`router.py` line 275 and ~367)

### Current (Flash, line 275)
```python
same_url_actions += 1
# Scroll down to reveal Continue button...
```

### Proposed (Flash, after line 275)
```python
same_url_actions += 1
if same_url_actions >= 6:
    return {"status": "failed", "reason": f"Stuck on same page ({same_url_actions} actions) — form too complex"}
# Scroll down to reveal Continue button...
```

### Same for Pro tier (~line 367)
```python
same_url_actions += 1
if same_url_actions >= 6:
    return {"status": "failed", "reason": f"Stuck on same page ({same_url_actions} actions) — form too complex"}
```

---

## Change 4: Transient Errors Don't Burn Budget (`batch_test.py` lines 226-245)

### Current
```python
status = result["status"]
reason = result.get("reason", "")
if status in ("success", "skipped", "disqualified"):
    success = True
elif url_attempts >= 2:
    total_failures += 1  # always counts
else:
    total_failures += 1  # always counts
```

### Proposed
```python
TRANSIENT_PATTERNS = ("Timeout", "Broken pipe", "JSONDecode", "HTTPConnectionPool", "TargetClosedError", "BrowserContext")

status = result["status"]
reason = result.get("reason", "")
is_transient = status == "failed" and any(p in reason for p in TRANSIENT_PATTERNS)

if status in ("success", "skipped", "disqualified"):
    success = True
    print(f"  ✅ Done with this URL ({status}).")
elif is_transient:
    # Infrastructure hiccup — don't count toward failure budget
    profile_idx += 1
    print(f"  ⚡ Transient error — not counting toward failures. Rotating profile.")
    if total_failures < MAX_FAILURES:
        await asyncio.sleep(SLEEP_BETWEEN)
    continue  # retry same URL with next profile
elif url_attempts >= 2:
    total_failures += 1
    ...
```

Note: the `while not success` loop + `continue` makes transient retries automatic.

---

## Change 5: Per-Job Cover Letter (`batch_test.py` lines 73-90, 165, 175-201)

### Current `_load_job_urls()` (line 73)
```python
urls = [row["apply_url"].strip() for row in reader if row.get("apply_url", "").strip()]
return urls
```

### Proposed
```python
jobs = []
for row in reader:
    url = row.get("apply_url", "").strip()
    doc_url = row.get("google_doc_id", "").strip()
    if url:
        jobs.append({"url": url, "doc_url": doc_url})
return jobs
```

### New helper function
```python
def _download_cover_letter(doc_url: str, job_id: str) -> str | None:
    """Download Google Doc as PDF, return local path."""
    if not doc_url:
        return None
    import re
    m = re.search(r'/d/([^/]+)', doc_url)
    if not m:
        return None
    doc_id = m.group(1)
    out_dir = "/tmp/cover_letters"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{job_id}.pdf")
    if os.path.exists(out_path):
        return out_path  # cached
    try:
        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=pdf"
        r = requests.get(export_url, timeout=15)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(r.content)
        print(f"  📄 Downloaded cover letter ({len(r.content)//1024}KB)")
        return out_path
    except Exception as e:
        print(f"  ⚠️ Cover letter download failed: {e} — using generic resume")
        return None
```

### Downstream changes
- `_RAW_URLS` becomes `_RAW_JOBS` (list of dicts)
- Dedup: `DEBUG_JOBS = [j for j in _RAW_JOBS if j["url"][:100] not in _ATTEMPTED]`
- Main loop: `for job in DEBUG_JOBS:` → `url = job["url"]`
- Before apply: `cover = _download_cover_letter(job["doc_url"], job_id) or resume`
- Call: `result = await apply_to_job(url, cover, profile_id)`
