# Manual Tasks — What You Need to Do

These are tasks Claude Code cannot do. They require your hands.

---

## 🔴 TASK 1 — Activate sessions for 18 profiles (P5)

**Do 1–2 profiles per day** to avoid Google flags.

For each profile:

1. Open AdsPower → launch that profile's browser
2. Go to `gmail.com` → log in with that profile's email (see `adspower_profiles` table for emails)
3. Go to `indeed.com` → Sign In → use the same Gmail account
4. AdsPower stores the session — that profile stays logged in permanently

**Then — one-time Indeed wizard (mandatory):**

5. Still in that AdsPower browser — find any receptionist job → click Easy Apply
6. Indeed shows a "complete your profile" wizard (name, phone, resume upload)
7. Fill it out and finish — this is required once per account or the pipeline hits a wall on first apply
8. You don't need to submit a real application — just complete the wizard

**Then:**

9. Update `adspower_profiles` in Supabase: set `cookie_status = 'active'` for that `user_id`

**Skip `k19td50a`** — it already has a valid session.

Do NOT use the Firefox inject script (`inject_firefox_cookies.py`) — that approach was deprecated. Log in directly inside AdsPower.

---

## 🟡 TASK 2 — Provide fresh job URLs for testing (P4)

When you're ready to run a test, you need to manually find 2–3 fresh job URLs from indeed.com.

- Search for "receptionist" jobs
- Choose simple postings with few questions
- Copy the full URL (should contain `viewjob?jk=`)
- Paste them when `batch_test.py` prompts you at startup

Old hardcoded URLs are stale — jobs are closed.

---

## 🟡 TASK 3 — Debug n8n HTTP request (P4)

n8n workflow is disconnected. It has an HTTP request at the end that should feed job URLs to the pipeline — it's not reaching it.

This is n8n debugging on your end, not Claude Code. Once fixed, production gets URLs automatically from n8n → pipeline.

---

## 🔵 TASK 4 — Per-profile resumes (P-NEXT)

Currently all profiles use the same `resume_oswaldo.pdf`. When you're ready to scale:

- Create 19 slightly varied resume PDFs
- Upload to VPS at `/opt/pipeline/resumes/<user_id>.pdf`
- Update `resume_path` in `adspower_profiles` per profile

Fine to skip until the pipeline is running cleanly.
