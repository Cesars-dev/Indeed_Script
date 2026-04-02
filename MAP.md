# Indeed Auto-Apply Pipeline — Master Map

> **One file to understand the entire project.**
> Last updated: 2026-03-13

---

## Workspace Root Structure

```
Indeed_Script/
├── README.md                    ← project intro + quick start
├── AGENTS.md                    ← AI agent protocol (read before working)
├── DOE_FRAMEWORK.md             ← D-O-E execution model
├── SURGEON_FRAMEWORK.md         ← audit→plan→cross-ref→execute methodology
├── MAP.md                       ← this file (master reference)
│
├── indeed-pipeline/             ← ALL active pipeline code (has its own README)
├── docs/                        ← knowledge base (what worked, what didn't)
├── workflow/                    ← N8N workflow JSON backup
├── mcp-stack/                   ← MCP server configs (Supabase, AdsPower)
│
├── .env                         ← master credentials (IDE MCP sources this)
├── .gitignore                   ← git config
├── package.json                 ← MCP npm deps
└── archive/                     ← old VPS info
```

---

## indeed-pipeline/ — Active Code (DOE-aligned)

```
indeed-pipeline/
├── README.md                    ← ENTRY POINT — architecture, rules
├── NEXT_STEPS.md                ← live task list (P5–P7 remaining)
│
├── directives/                  ← D LAYER — goals, memory, SOPs
│   ├── memory.md                ← current state, what's done, what's next
│   ├── execution_map.md         ← "go" decision tree — what to run
│   ├── infrastructure.md        ← credentials, VPS, Supabase, profile map
│   ├── browser_automation.md    ← nodriver vs playwright, CDP rules
│   ├── sessions_accounts.md     ← session lifecycle, Gmail, profile health
│   ├── smartapply_form.md       ← form flow, Gemini loop, gaps
│   ├── stealth.md               ← fingerprint/CF stealth architecture
│   └── fingerprint_sync.md      ← AdsPower fingerprint → Supabase flow
│
├── src/                         ← E LAYER — VPS-side application code
│   ├── playwright_indeed.py     ← 🔥 BROWSER ENGINE (Playwright + Gemini Vision)
│   ├── smartapply/              ← SmartApply v2 router (6-shot engine)
│   │   ├── router.py            ← deterministic → Flash → Pro escalation
│   │   ├── dom_scanner.py       ← DOM scanning (<100ms)
│   │   ├── handlers.py          ← deterministic form handlers
│   │   ├── gemini_fallback.py   ← Gemini vision fallback
│   │   ├── logger.py            ← fire-and-forget async Supabase logger
│   │   └── patterns.py          ← form element patterns
│   ├── apply_runner.py          ← job loop: CSV → dedup → rotate → apply
│   ├── orchestrator.py          ← cron entry point → triggers N8N
│   ├── webhook_server.py        ← VPS HTTP :8080 → receives CSV from N8N
│   ├── supabase_client.py       ← DB helpers: search combos, log execution
│   └── gdrive_client.py         ← download proposal DOCX → PDF
│
├── scripts/                     ← E LAYER — Mac-side utility scripts
│   ├── batch_test.py            ← primary test runner (stdin URLs)
│   ├── tunnel.sh                ← SSH tunnel Mac↔VPS
│   ├── vps_adspower.sh          ← AdsPower lifecycle: start/stop/status/diagnose
│   ├── audit_keys.sh            ← credential leak scanner
│   ├── read_fingerprints.py     ← read AdsPower fingerprints → Supabase
│   ├── setup_profiles.py        ← ⚠️ DANGER: recreates all profiles
│   ├── test_playwright.py       ← CDP connection verifier
│   ├── test_mac_apply.py        ← Mac-side apply test
│   ├── supabase_mcp.py          ← Supabase MCP bridge
│   └── vps_start.sh / vps_stop.sh  ← VPS-side AdsPower scripts
│
├── docs/                        ← reference docs (prompts, schemas)
│   ├── gemini_prompt.md         ← Gemini prompt reference
│   └── adspower_kernel_prompt.md ← AdsPower kernel config
│
├── archive/                     ← completed work (read-only)
│   ├── tasks_done/              ← completed surgeon framework tasks
│   ├── memory_old/              ← old memory files (01-11, superseded)
│   ├── orphan_docs/             ← archived .md files
│   ├── nodriver/                ← nodriver era code (M7-M22)
│   └── milestones_history/      ← raw milestone files
│
├── .env                         ← pipeline credentials (NEVER commit)
├── .env.example                 ← credential template
├── supabase_schema.sql          ← DB schema reference
├── requirements.txt             ← Python deps
└── resume_oswaldo.pdf           ← shared resume (until per-profile P7)
```

---

## docs/ — Root Knowledge Base

```
docs/
├── what_worked/                 ← proven approaches (read before trying new)
│   ├── 1_ssh_tunnel_to_mac_adspower.md
│   ├── 2_adspower_vps_service_stable.md
│   ├── 3_pipeline_milestones_1_to_6.md
│   ├── 4_cookie_extraction_via_adspower_cdp.md
│   └── adspower_vps_sync.md
├── what_didnt/                  ← dead ends (NEVER retry)
│   ├── 1_nodriver_headless_on_vps_blocked.md
│   ├── 2_adspower_cloud_auth_via_api_key_flag.md
│   ├── 3_datacenter_ips_blocked_by_indeed.md
│   ├── 4_ubuntu24_apt_package_gotchas.md
│   └── 5_nodriver_cookie_injection_approach.md
└── screenshots/
```

---

## System Architecture

```
[DAILY CRON 9AM — VPS]
        │
        ▼
orchestrator.py ──→ Supabase (search_combinations) ──→ N8N webhook
                                                              │
                                                    N8N scrapes Indeed
                                                    GPT-4 filters
                                                    Claude writes proposals
                                                    Saves to Google Drive
                                                              │
                                                    POST CSV URL → VPS:8080
                                                              │
        ┌─────────────────────────────────────────────────────┘
        ▼
webhook_server.py (port 8080, systemd, always on)
        │
        ▼
apply_runner.py
  ├─ download CSV
  ├─ for each job:
  │   ├─ Supabase dedup check
  │   ├─ Google Drive → download DOCX → LibreOffice → PDF
  │   ├─ pick AdsPower profile (round-robin, 19 profiles)
  │   └─ playwright_indeed.apply_to_job()
  │         ├─ AdsPower API → start profile → debug_port
  │         ├─ rebrowser-playwright.connect_over_cdp(port)
  │         ├─ indeed.com warmup (10-15s, human-like)
  │         ├─ navigate to job → click Apply button
  │         └─ SmartApply v2 router (50 steps max):
  │               DOM scan → deterministic → Flash → Pro
  │               until: done / failed / disqualified
  └─ sb_log() → Supabase (fire-and-forget, non-blocking)
```

---

## Quick Reference

| Need | Command/File |
|------|------|
| Start tunnel | `bash indeed-pipeline/scripts/tunnel.sh` |
| Start AdsPower on VPS | `bash indeed-pipeline/scripts/vps_adspower.sh start` |
| Stop AdsPower on VPS | `bash indeed-pipeline/scripts/vps_adspower.sh stop` |
| Run pipeline test | `cd indeed-pipeline && PYTHONUNBUFFERED=1 PYTHONPATH=venv_local/lib/python3.13/site-packages python3.13 -u scripts/batch_test.py` |
| Scan for leaked keys | `bash indeed-pipeline/scripts/audit_keys.sh` |
| Deploy to VPS | `git push` then `ssh root@45.55.90.156 "cd /root/indeed-pipeline && git pull && systemctl restart indeed-webhook"` |
| Check what's next | [`indeed-pipeline/NEXT_STEPS.md`](indeed-pipeline/NEXT_STEPS.md) |
| Current state | [`indeed-pipeline/directives/memory.md`](indeed-pipeline/directives/memory.md) |
| Decision tree | [`indeed-pipeline/directives/execution_map.md`](indeed-pipeline/directives/execution_map.md) |
