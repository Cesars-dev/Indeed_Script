# AGENTS.md — Operating Protocol

> For any AI agent (Antigravity, Claude, GPT, etc.) working in this project.
> This is a **protocol document**. Follow it in order.
> Execution model: **DOE Framework** (see `DOE_FRAMEWORK.md`)

---

## What is this project?

An automated Indeed job application system. It scrapes listings, generates tailored cover letters, then applies via 19 rotating browser profiles that mimic human behavior. The core challenge is evading Indeed's bot detection at the browser fingerprint, timing, and behavioral level.

**Current stage:** Apply engine fully built (P0–P4 done). Sessions activation (P5) and search warmup (P6) remaining.

---

## STEP 1 — READ (before touching anything)

Read these files in order. Do not act until done.

```
1. indeed-pipeline/README.md                      ← architecture, folder guide
2. indeed-pipeline/NEXT_STEPS.md                   ← your task list for this session
3. indeed-pipeline/directives/ (relevant files):
     memory.md                                     ← current state, what's done/next
     execution_map.md                              ← decision tree: "go" → run THIS
     infrastructure.md                             ← VPS, AdsPower, Supabase, ports
     browser_automation.md                         ← CDP rules, stealth, why Playwright
     sessions_accounts.md                          ← profiles, sessions, accounts
     smartapply_form.md                            ← Gemini loop, form behavior
     stealth.md                                    ← fingerprint/CF stealth decisions
4. docs/what_didnt/                                ← dead ends — NEVER re-try
```

**Make decisions based on what these files say — not assumptions.**
If a file contradicts your assumption, the file wins.

---

## STEP 2 — PLAN (before writing a single line)

Use the **Surgeon Framework** (`SURGEON_FRAMEWORK.md`):
1. **Audit** — cross-reference task against actual code
2. **Action Plan** — list exact changes with line numbers
3. **Cross-Reference** — verify audit ↔ plan alignment
4. **Execute** — cut code only after user approval

Rules:
- Only work on tasks from `NEXT_STEPS.md`. Don't invent scope.
- Check `directives/` before writing any new logic — it may be solved already.
- Never re-try approaches in `docs/what_didnt/`.
- Test before declaring something done.

---

## STEP 3 — UPDATE (after every discovery)

| What happened | Update |
|--------------|--------|
| New knowledge gained | Relevant `directives/*.md` file |
| Blocker resolved or found | `NEXT_STEPS.md` |
| Approach confirmed dead | `docs/what_didnt/` |
| Architecture decision made | `directives/stealth.md` or relevant directive |
| Session ended | Update `NEXT_STEPS.md` + `directives/memory.md` |

---

## Deploy

```bash
# We are ON the VPS. Deploy = git pull + restart.
cd /root/indeed-pipeline && git pull && systemctl restart indeed-webhook
```

---

## VPS Operations (all local — no tunnels)

### AdsPower
```bash
systemctl start xvfb && systemctl start adspower     # start
systemctl stop adspower && systemctl stop xvfb        # stop
systemctl status adspower xvfb                        # check
bash scripts/vps_adspower.sh diagnose                 # full dump
```

### Run pipeline test
```bash
cd indeed-pipeline
PYTHONUNBUFFERED=1 PYTHONPATH=venv_local/lib/python3.13/site-packages python3.13 -u scripts/batch_test.py
```

---

## Security Rules

1. **Never hardcode API keys** — all secrets in `.env` only
2. **`.env` is never in git** — it's in `.gitignore`
3. **Run `indeed-pipeline/scripts/audit_keys.sh`** before any commit to scan for leaked keys

---

## MCP Tools Available

- **Supabase MCP** — query/update DB directly (`supabase_indeed` + `supabase_leads`)
- **Firecrawl MCP** — web research when needed
- **GitHub MCP** — repo operations
