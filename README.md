# Indeed Auto-Apply Pipeline

> Fully automated job application system — AdsPower + Playwright + Gemini Vision
> **Status:** Apply engine fully built (P0–P4 done). Sessions activation (P5) and search warmup (P6) remaining.

---

## What is this?

This pipeline scrapes Indeed job listings daily via N8N + Apify, then automatically applies using 19 rotating anti-detect browser profiles. Gemini 2.5 Flash Vision reads each SmartApply form screenshot and decides the next action — zero hardcoded selectors.

**Stack:** AdsPower (fingerprint spoofing) → Playwright CDP → Gemini 2.5 Flash → Supabase log

---

## Frameworks

| Framework | File | Purpose |
|-----------|------|---------|
| **DOE** | [`DOE_FRAMEWORK.md`](DOE_FRAMEWORK.md) | Directive → Orchestration → Execution model |
| **Surgeon** | [`SURGEON_FRAMEWORK.md`](SURGEON_FRAMEWORK.md) | Audit → Plan → Cross-ref → Execute methodology |

All agents follow DOE for task routing and Surgeon for code changes.

---

## Folder Structure

```
Indeed_Script/
├── README.md              ← this file
├── AGENTS.md              ← agent protocol (read before working)
├── DOE_FRAMEWORK.md       ← D-O-E execution model
├── SURGEON_FRAMEWORK.md   ← audit → plan → execute methodology
├── MAP.md                 ← full project map
│
├── indeed-pipeline/       ← ALL active pipeline code
│   ├── directives/        ← D layer: memory, SOPs, execution map
│   ├── src/               ← E layer: application code
│   ├── scripts/           ← E layer: utility scripts
│   └── NEXT_STEPS.md      ← live task list
│
├── docs/                  ← knowledge base (what worked, what didn't)
├── workflow/              ← N8N workflow JSON backup
├── mcp-stack/             ← MCP server configs
│
├── .env                   ← master credentials
└── package.json           ← MCP npm deps
```

---

## How to approach it

Read in this order. Do not skip. Do not act until done.

1. **[`AGENTS.md`](AGENTS.md)** — protocol, rules, frameworks
2. **[`indeed-pipeline/NEXT_STEPS.md`](indeed-pipeline/NEXT_STEPS.md)** — your task list
3. **[`indeed-pipeline/directives/memory.md`](indeed-pipeline/directives/memory.md)** — current state
4. **[`indeed-pipeline/directives/execution_map.md`](indeed-pipeline/directives/execution_map.md)** — what "go" means
5. **Relevant [`directives/`](indeed-pipeline/directives/) files** — deep knowledge per topic

---

## VPS (we are ON the VPS)

All development and execution happens locally on the VPS. No Mac tunnels.

| | |
|--|--|
| SSH | `root@45.55.90.156` |
| Dev path | `/home/julio/projects/Indeed_Script/indeed-pipeline/` |
| Deploy path | `/root/indeed-pipeline/` |

### AdsPower (local)

```bash
systemctl start xvfb && systemctl start adspower     # start
systemctl stop adspower && systemctl stop xvfb        # stop
systemctl status adspower xvfb                        # check
bash scripts/vps_adspower.sh diagnose                 # full dump
```

### Deploy

```bash
cd /root/indeed-pipeline && git pull && systemctl restart indeed-webhook
```

### Run pipeline test

```bash
cd indeed-pipeline
PYTHONUNBUFFERED=1 PYTHONPATH=venv_local/lib/python3.13/site-packages python3.13 -u scripts/batch_test.py
```

---

## Supabase

Two projects.

| Project | MCP ID | URL |
|---------|--------|-----|
| **Indeed Auto-Apply** | `supabase_indeed` | `https://uckkgnqlehprbpypcgjc.supabase.co` |
| **LinkedIn Leads** | `supabase_leads` | `https://rvjuymgbarospuwkkxhc.supabase.co` |

No RLS on any table. Anon key has full access.

### `.env` note

- **`Indeed_Script/.env`** — master env, IDE MCP sources `SUPABASE_ACCESS_TOKEN` from here
- **`indeed-pipeline/.env`** — pipeline env, Python scripts source `SUPABASE_URL`, `SUPABASE_KEY` from here

---

## Reference

| Need | File |
|------|------|
| Full project map | [`MAP.md`](MAP.md) |
| Agent protocol | [`AGENTS.md`](AGENTS.md) |
| DOE Framework | [`DOE_FRAMEWORK.md`](DOE_FRAMEWORK.md) |
| Surgeon Framework | [`SURGEON_FRAMEWORK.md`](SURGEON_FRAMEWORK.md) |
| Live task list | [`indeed-pipeline/NEXT_STEPS.md`](indeed-pipeline/NEXT_STEPS.md) |
| Current state | [`indeed-pipeline/directives/memory.md`](indeed-pipeline/directives/memory.md) |
| Execution map | [`indeed-pipeline/directives/execution_map.md`](indeed-pipeline/directives/execution_map.md) |
| Stealth decisions | [`indeed-pipeline/directives/stealth.md`](indeed-pipeline/directives/stealth.md) |
| Dead ends — never retry | [`docs/what_didnt/`](docs/what_didnt/) |
