# Execution Map — What "go" means right now
> Updated: 2026-03-13

---

## Current Priority: P5 (manual) + P6 (code)

### If user says "go" → run a test apply
```bash
cd indeed-pipeline
PYTHONUNBUFFERED=1 PYTHONPATH=venv_local/lib/python3.13/site-packages python3.13 -u scripts/batch_test.py
```
Paste job URLs when prompted. Uses profile `k1a2vupc`.

### If user says "deploy" → sync to VPS
```bash
# Option A: git (preferred)
ssh root@45.55.90.156 "cd /root/indeed-pipeline && git pull"
ssh root@45.55.90.156 "systemctl restart indeed-webhook"

# Option B: scp (if git not set up on VPS)
scp -r indeed-pipeline/src/ root@45.55.90.156:/root/indeed-pipeline/
ssh root@45.55.90.156 "systemctl restart indeed-webhook"
```

### If user says "tunnel" → connect Mac to VPS
```bash
bash indeed-pipeline/scripts/tunnel.sh
```

### If user says "adspower" → manage VPS AdsPower
```bash
bash indeed-pipeline/scripts/vps_adspower.sh start|stop|status|diagnose
```

---

## Decision Tree

```
User request
    │
    ├── "test" / "apply" / "run"
    │       → scripts/batch_test.py (paste URLs)
    │
    ├── "deploy" / "push"
    │       → git push + VPS git pull + restart service
    │
    ├── "fix X" / "add Y"
    │       → Read directives/ → Surgeon Framework → Execute
    │
    ├── "check status"
    │       → Read NEXT_STEPS.md + directives/memory.md
    │
    └── "activate session"
            → Manual: AdsPower → Gmail login → Indeed login → mark active in Supabase
```

---

## Scripts Reference

| Script | Purpose | Layer |
|--------|---------|-------|
| `scripts/batch_test.py` | Test apply (stdin URLs) | E |
| `scripts/tunnel.sh` | SSH tunnel Mac↔VPS | E |
| `scripts/vps_adspower.sh` | AdsPower lifecycle on VPS | E |
| `scripts/audit_keys.sh` | Credential leak scan | E |
| `scripts/read_fingerprints.py` | Read AdsPower fingerprints → Supabase | E |
| `scripts/setup_profiles.py` | ⚠️ DANGER: recreate all profiles | E |
