# Apply Tests — Debug URLs

Use these for pipeline debugging. Run one at a time.

## URLs

```
https://www.indeed.com/viewjob?jk=b5323afd8d319c8e&tk=1jjjllol6h3m0807&from=hp.jobsForYou&vjs=3
https://www.indeed.com/viewjob?jk=5ebf121cb2dcf951&vjs=3
```

## Profiles

| Profile ID   | Name                    | Session  |
|--------------|-------------------------|----------|
| `k19td50a`   | Oswaldin Lara (S10)     | active   |
| `k1a2vupc`   | Gabriela Rodrigues (S19)| pending  |

## Debug Strategy

- Alternate profiles on each failure
- Stop after 5 total failures
- Check screenshots in `/tmp/playwright_debug/`
- Log every step to Supabase `apply_step_log`
