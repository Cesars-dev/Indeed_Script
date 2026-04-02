# Recover a Claude Session

## The Problem
- VSCode Claude extension creates sessions with its own binary (v2.1.63)
- Terminal `claude` command uses npm package (v2.1.41) — different version, can't find sessions
- `claude --resume <id>` from terminal returns "No conversation found"

## The Fix — Use the Extension's Own Binary

```bash
cd /Users/Cesar_1/Documents/Trabajo/AI/IDE/experiments/Script && \
/Users/Cesar_1/.vscode/extensions/anthropic.claude-code-2.1.63-darwin-x64/resources/native-binary/claude \
--resume f5557fb7-557b-42a5-ab82-c7102e32f09b
```

> **Must run from external Terminal.app — NOT the VSCode integrated terminal.**
> (VSCode terminal blocks nested Claude sessions via `CLAUDECODE` env var)

---

## Interactive Picker (if you don't have the session ID)

```bash
cd /Users/Cesar_1/Documents/Trabajo/AI/IDE/experiments/Script && \
/Users/Cesar_1/.vscode/extensions/anthropic.claude-code-2.1.63-darwin-x64/resources/native-binary/claude \
--resume
```

Arrow keys to navigate, Enter to open.

---

## Resume Most Recent Session

```bash
cd /Users/Cesar_1/Documents/Trabajo/AI/IDE/experiments/Script && \
/Users/Cesar_1/.vscode/extensions/anthropic.claude-code-2.1.63-darwin-x64/resources/native-binary/claude \
--continue
```

---

## Finding a Session ID Without the UI

Sessions are stored as JSONL files. List them:

```bash
ls ~/.claude/projects/-Users-Cesar-1-Documents-Trabajo-AI-IDE-experiments-Script/
```

Each `.jsonl` filename = a session ID.

To peek at what a session was doing:

```bash
tail -3 ~/.claude/projects/-Users-Cesar-1-Documents-Trabajo-AI-IDE-experiments-Script/<session-id>.jsonl \
| python3 -c "
import sys, json
for line in sys.stdin:
    try:
        d = json.loads(line)
        c = d.get('message',{}).get('content','')
        if isinstance(c, list):
            for x in c:
                if x.get('type')=='text': print(x['text'][:300])
        elif c: print(c[:300])
    except: pass
"
```

---

## Mirror a Live Session (read-only tail)

```bash
nohup bash -c '
SESSION=~/.claude/projects/-Users-Cesar-1-Documents-Trabajo-AI-IDE-experiments-Script/<session-id>.jsonl
LAST=0
while true; do
    CUR=$(wc -l < "$SESSION")
    if [ "$CUR" -gt "$LAST" ]; then
        tail -n "+$((LAST+1))" "$SESSION" | python3 -c "
import sys,json
for l in sys.stdin:
    try:
        d=json.loads(l); m=d.get(\"message\",{}); c=m.get(\"content\",\"\")
        r=m.get(\"role\",d.get(\"type\",\"\"))
        if isinstance(c,list):
            for x in c:
                if x.get(\"type\")==\"text\": print(f\"[{r}] {x[\"text\"][:400]}\")
                elif x.get(\"type\")==\"tool_use\": print(f\"[tool] {x[\"name\"]}\")
        elif c: print(f\"[{r}] {c[:400]}\")
    except: pass
"
        LAST=$CUR
    fi
    sleep 300
done
' > /tmp/session_mirror.log 2>&1 &
```

Then check updates anytime:
```bash
cat /tmp/session_mirror.log
```

---

## Key Notes
- Session directory is scoped to the project path — always `cd` into the project first
- Sessions survive process restarts as long as the `.jsonl` file exists
- Extension binary path will change when the extension updates — check `~/.vscode/extensions/anthropic.claude-code-*/` for the current version
