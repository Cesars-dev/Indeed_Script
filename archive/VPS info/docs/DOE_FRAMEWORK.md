# 📐 DOE Framework — How to Execute Tasks

> This framework governs how ALL work is done inside any project using agent_os.
> Mode tells you HOW to access the VPS. DOE tells you HOW to do the work once you're in.

---

## The 3 Layers

```
┌─────────────────────────────────────────────────────────┐
│  D — Directive       What to do (written by human/agent)│
│      directives/     Goals, rules, edge cases, SOPs     │
└─────────────────────────────────┬───────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────┐
│  O — Orchestration   You. Decision making.              │
│      (this agent)    Read → Route → Handle → Update     │
└─────────────────────────────────┬───────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────┐
│  E — Execution       Deterministic scripts              │
│      execution/      Python, bash — do the actual work  │
└─────────────────────────────────────────────────────────┘
```

---

## D — Directive (What to do)

- Written in Markdown, lives in `directives/` inside each project
- Defines: goals, inputs, tools to use, outputs, edge cases, constraints
- Think of it as an SOP — what you'd give a competent mid-level employee
- **Directives are living documents.** Update them when you learn something new (API limits, edge cases, better approaches)
- Do NOT overwrite directives without asking, unless explicitly told to

**Key files:**
```
directives/
├── memory.md          ← current project state, what broke, what's next
├── execution_map.md   ← decision tree: when user says "go", run THIS
└── *.md               ← task-specific SOPs
```

---

## O — Orchestration (Your role)

You are the O layer. Your job:

1. **Read** the relevant directive(s) first — always
2. **Route** — decide which script to call, in which order, with which inputs
3. **Handle errors** — read stack trace, fix script, test, move on
4. **Update** — write what you learned back into the directive

**Rules:**
- Never do manually what a script can do deterministically
- Never run paid API calls (Apify, OpenAI, Anthropic) without explicit user confirmation
- Never create new directives without asking first
- Be the decision layer. Not the execution layer.

---

## E — Execution (The work)

- Deterministic scripts in `execution/` (Python, bash)
- Handles: API calls, data processing, database writes, file ops
- Reliable and testable — if you'd do something more than once, it must be a script
- Scripts receive inputs via args or `.env`. Never inline credentials.

**Key rule:** If you catch yourself doing something repetitive manually — stop. Write a script, put it in `execution/`, then call it.

---

## Why DOE Works

> 90% accuracy per step → 59% success over 5 chained steps.

Push complexity into deterministic E-layer code. You (the O layer) focus only on decisions. The system compounds improvement over time instead of compounding errors.

---

## Self-Annealing Loop

When something breaks — don't escalate. Fix it and make the system stronger:

```
Error occurs
    │
    ▼
Read error + stack trace
    │
    ▼
Fix the script in execution/
    │
    ▼
Test it — confirm it works
    │
    ▼
Update the directive with what you learned
    │
    ▼
System is now stronger than before ✅
```

> **Exception:** If the fix requires re-running paid API calls → **confirm with user first**.

---

## DOE in Practice — Session Flow

```
1. Read directives/memory.md       ← what happened last session
2. Read directives/execution_map.md ← what "go" means right now
3. Identify which script to call   ← O layer routing
4. Call it: python3 execution/your_script.py
5. Handle any errors               ← self-anneal
6. Update directives with learnings
7. Safe push: ./agent_os/scripts/gatekeeper.sh "what was done"
```

---

> _Part of the agent_os framework. Reference from AGENTS.md after mode selection._
