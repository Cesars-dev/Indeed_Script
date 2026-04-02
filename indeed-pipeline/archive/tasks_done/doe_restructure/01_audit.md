# Folder Structure Audit — DOE Framework Alignment
> Date: 2026-03-13

---

## DOE Expects

```
project-root/
├── AGENTS.md              ← agent protocol
├── DOE_FRAMEWORK.md       ← this framework
├── directives/            ← D layer: goals, memory, execution map, SOPs
│   ├── memory.md          ← current state, what broke, what's next
│   ├── execution_map.md   ← decision tree: when user says "go", run THIS
│   └── *.md               ← task-specific SOPs
├── execution/             ← E layer: deterministic scripts
│   ├── *.py               ← Python scripts
│   └── *.sh               ← Bash scripts
└── src/                   ← application source code
```

---

## What Actually Exists (audit)

```
Indeed_Script/                          ← ROOT
├── AGENTS.md                          ✅ correct location
├── DOE_FRAMEWORK.md                   ✅ just moved here
├── MAP.md                             ⚠️ outdated (references SESSION_TODO, old warmup times)
├── README.md                          ✅ project intro
├── .env                               ✅ master credentials
│
├── indeed-pipeline/                   ← ALL pipeline code
│   ├── README.md                      ⚠️ references old structure
│   ├── NEXT_STEPS.md                  ✅ live task list (just updated)
│   ├── PIPELINE_STATUS.md             ⚠️ potentially stale
│   ├── CLAUDE.md                      ⚠️ old agent instructions (superseded by AGENTS.md)
│   ├── USER_README.md                 ⚠️ manual tasks doc
│   ├── action_plan.md                 ⚠️ old action plan (orphan)
│   ├── deep_search_eval.md            → should be in directives/
│   ├── memory_2026-03-05.md           ⚠️ old memory dump (superseded by memory/)
│   ├── memory_2026-03-06.md           ⚠️ old memory dump (superseded by memory/)
│   │
│   ├── memory/                        ← D layer equivalent (14 files)
│   │   ├── 01-05: infrastructure, browser, sessions, form, current state
│   │   ├── 06-11: debug sessions, refactors, fingerprint sync
│   │   ├── surgeon_framework.md       → should be in root (like DOE_FRAMEWORK.md)
│   │   └── deep_research_prompt_stealth.md → reference doc, not memory
│   │
│   ├── docs/                          ← 3 files (prompt refs, bypass plan)
│   │   ├── gemini_prompt.md           → reference doc
│   │   ├── adspower_kernel_prompt.md  → reference doc
│   │   └── turnstile_bypass_plan.md   → DONE, should be archived
│   │
│   ├── tasks/                         ← surgeon framework task folders
│   │   ├── p2_execution_logging/      ← just completed
│   │   ├── fingerprint_sync/
│   │   └── rebrowser_cdp_fix/
│   │
│   ├── src/                           ← ✅ application code (E layer)
│   ├── scripts/                       ← ✅ utility scripts (E layer)
│   ├── archive/                       ← ✅ old code
│   └── supabase_schema.sql            ✅ DB reference
│
├── docs/                              ← root-level knowledge base
│   ├── what_worked/                   ✅ 
│   ├── what_didnt/                    ✅ 
│   └── AUDIT_profiles.md             ⚠️ stale audit
│
├── workflow/                          ← n8n backup
│   └── Indeed Proposal generator.json ✅
│
├── mcp-stack/                         ← MCP server configs
├── archive/                           ← root archive (VPS info)
└── Indeed_Script/                     ⚠️ empty folder (just a .gitignore)
```

---

## Problems Identified

| # | Problem | Fix |
|---|---------|-----|
| 1 | **No `directives/` folder** — DOE expects it. Memory files = directives but scattered | Create `directives/` at pipeline level, consolidate |
| 2 | **No `execution_map.md`** — DOE says "when user says go, run THIS" | Create `directives/execution_map.md` from NEXT_STEPS info |
| 3 | **Orphan .md files in pipeline root** — `action_plan.md`, `memory_2026-03-*.md`, `CLAUDE.md`, `PIPELINE_STATUS.md` | Archive or delete |
| 4 | **MAP.md outdated** — references `SESSION_TODO.md` (deleted), old warmup times, old deploy method | Update |
| 5 | **`surgeon_framework.md` in memory/** — it's a methodology, not project memory | Move to root like DOE_FRAMEWORK.md |
| 6 | **`Indeed_Script/Indeed_Script/`** — empty nested folder with just .gitignore | Delete |
| 7 | **Completed tasks in `tasks/`** — should be archived after completion | Move to `archive/tasks/` |
| 8 | **`turnstile_bypass_plan.md` in docs/** — P1.5 is done, plan is obsolete | Archive |

---

## Proposed Structure (DOE-aligned)

```
Indeed_Script/
├── AGENTS.md                          ← agent protocol (keep)
├── DOE_FRAMEWORK.md                   ← framework (keep)
├── MAP.md                             ← master map (UPDATE)
├── README.md                          ← project intro (keep)
├── .env                               ← credentials (keep)
│
├── indeed-pipeline/
│   ├── README.md                      ← pipeline entry point (UPDATE paths)
│   ├── NEXT_STEPS.md                  ← live task list (keep, just updated)
│   │
│   ├── directives/                    ← D LAYER (NEW — consolidate from memory/)
│   │   ├── memory.md                  ← current state (from 05_current_state_next.md)
│   │   ├── execution_map.md           ← "go" decision tree (NEW)
│   │   ├── infrastructure.md          ← from 01_infrastructure.md
│   │   ├── browser_automation.md      ← from 02_browser_automation.md
│   │   ├── sessions_accounts.md       ← from 03_sessions_accounts.md
│   │   ├── smartapply_form.md         ← from 04_smartapply_form.md
│   │   ├── stealth.md                 ← from deep_search_eval.md
│   │   └── fingerprint_sync.md        ← from 11_fingerprint_sync_session.md
│   │
│   ├── src/                           ← E LAYER: application code (keep)
│   ├── scripts/                       ← E LAYER: utility scripts (keep)
│   │
│   ├── archive/                       ← completed work
│   │   ├── tasks/                     ← completed surgeon tasks
│   │   ├── memory/                    ← old numbered memory files
│   │   └── ...existing archive...
│   │
│   ├── docs/                          ← reference docs (prompts, schema)
│   │   ├── gemini_prompt.md
│   │   └── adspower_kernel_prompt.md
│   │
│   ├── supabase_schema.sql            ← DB reference (keep)
│   ├── requirements.txt               ← deps (keep)
│   └── resume_oswaldo.pdf             ← shared resume (keep)
│
├── docs/                              ← root knowledge base (keep)
│   ├── what_worked/
│   └── what_didnt/
│
├── workflow/                          ← n8n backup (keep)
└── mcp-stack/                         ← MCP configs (keep)
```

### Files to DELETE
- `Indeed_Script/Indeed_Script/` (empty)
- `indeed-pipeline/CLAUDE.md` (superseded by AGENTS.md)
- `indeed-pipeline/PIPELINE_STATUS.md` (superseded by NEXT_STEPS.md)
- `indeed-pipeline/USER_README.md` (merge into README if needed)
- `indeed-pipeline/action_plan.md` (orphan, old)
- `indeed-pipeline/memory_2026-03-05.md` (superseded by memory/)
- `indeed-pipeline/memory_2026-03-06.md` (superseded by memory/)

### Files to ARCHIVE
- `indeed-pipeline/memory/06-10` (old session notes, not active directives)
- `indeed-pipeline/tasks/*` (completed work)
- `indeed-pipeline/docs/turnstile_bypass_plan.md` (done)
- `docs/AUDIT_profiles.md` (stale)

### Files to MOVE
- `memory/surgeon_framework.md` → root (alongside DOE_FRAMEWORK.md)
