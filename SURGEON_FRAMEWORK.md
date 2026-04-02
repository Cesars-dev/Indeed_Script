---
description: The Surgeon Framework — audit, plan, cross-reference, master plan, execute only when airtight
---

# 🔪 The Surgeon Framework

**Never cut until you know exactly where the blade goes.**

## Steps

### 1. AUDIT
- Read every file involved
- Trace every call, every data flow, every dependency
- Document what EXISTS vs what's MISSING
- Find bugs, risks, conflicts
- Output: `{phase}_audit.md`

### 2. ACTION PLAN
- Write the fix based on the audit
- Step-by-step, with code patterns, SQL schemas, file changes
- Output: `{phase}_action_plan.md`

### 3. CROSS-REFERENCE
- Compare the **two files** (audit + action plan) against each other
- Does the plan address every issue the audit found?
- Does the audit support every change the plan proposes?
- Find contradictions, gaps, redundancies between the two docs
- Output: `{phase}_cross_reference.md`

### 4. PREFLIGHT
- Take the cross-reference results and verify against the **ACTUAL CODE**
- Trace every claim against real line numbers — is it still true?
- Trace every planned change against real function signatures — will it work?
- Fix every flaw found, resolve all open items
- Output: `{phase}_master_plan.md` (airtight, all flaws resolved)
- Archive source files → `tasks/archive/`

### 5. EXECUTE — ONLY WHEN AIRTIGHT
- Do NOT touch code until the master plan has zero open issues
- User reviews and approves first
- Execute step by step, compile-check after each step
- Test at the end

## Rules
- **No shortcuts.** Every step produces a file.
- **No assumptions.** If you haven't read the code, you don't know what it does.
- **No silent failures.** If a flaw is found, it goes in the doc — not swept under the rug.
- **Archive completed plans.** Only the active master plan lives in `tasks/`.
