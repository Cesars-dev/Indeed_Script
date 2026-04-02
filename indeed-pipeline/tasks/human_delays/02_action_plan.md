# Action Plan: Human-Like Delays

## Change 1 — handlers.py L30: Post-upload wait
```python
# FROM:
await asyncio.sleep(1)
# TO:
await asyncio.sleep(random.uniform(2.0, 4.0))
```

## Change 2 — handlers.py L149: Post-text-fill dwell
```python
# FROM:
await asyncio.sleep(0.3)
# TO:
await asyncio.sleep(random.uniform(0.8, 1.5))
```

## Change 3 — handlers.py L265: Post-button-click wait
```python
# FROM:
await asyncio.sleep(0.5)
# TO:
await asyncio.sleep(random.uniform(2.0, 4.0))
```

## Change 4 — router.py L116: Post-scroll read time
```python
# FROM:
await asyncio.sleep(0.3)
# TO:
await asyncio.sleep(random.uniform(0.8, 1.5))
```

## Change 5 — router.py L140: Post-deterministic-success gap
```python
# FROM:
await asyncio.sleep(0.5)  # page reaction time
# TO:
await asyncio.sleep(random.uniform(1.5, 3.0))  # human reads result before moving on
```

## NOT changing (Gemini calls already add 10-15s):
- router.py L173: `sleep(0.5)` after Flash — kept (Gemini API = natural delay)
- router.py L208: `sleep(0.5)` after Pro — kept (same reason)

## Total: 5 changes across 2 files
