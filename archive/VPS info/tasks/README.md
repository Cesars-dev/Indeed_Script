# tasks/ — Task Queue

> Drop `.md` files here. The agent will list them at session start and ask which one to tackle.

---

## How to add a task

Create a new `.md` file in this folder. Keep it simple:

```
# Task: <short title>

## What to do
Clear description of what needs to be done.

## Success looks like
What done means — specific, verifiable output.

## Notes / constraints
Any edge cases, tools to use, or things to avoid.
```

---

## How the agent uses this

1. Agent lists all `.md` files in `tasks/` at session start
2. User picks one (or describes a new task)
3. Agent reads the task file
4. Agent applies DOE framework to execute it (`docs/DOE_FRAMEWORK.md`)
5. Agent marks task complete or updates the file with findings

---

## Example

> `tasks/sync_env_to_vps.md`
> `tasks/deploy_new_scraper.md`
> `tasks/debug_pipeline_timeout.md`

No tasks yet — add your first one.
