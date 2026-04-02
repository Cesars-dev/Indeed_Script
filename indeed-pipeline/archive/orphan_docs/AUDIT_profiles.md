# Profile Audit — AdsPower × JSON × Supabase
> Date: 2026-03-02
> Source of truth: **AdsPower** (live, 9 profiles in group `indeed`)
> Proxy creds (all profiles): `lehavxel / 4lzagcbkv7t9` · socks5

---

## Part 1 — AdsPower vs `config/accounts.json`

| Slot | user_id | Name (remark) | Email | Proxy (AdsPower) | Last IP | Last Opened | JSON email ✓ | JSON user_id ✓ |
|------|---------|--------------|-------|-----------------|---------|-------------|-------------|----------------|
| 01 | k19td4st | Gabriela Lopez Gomez | gabrielalopezgomez80@gmail.com | 142.111.227.167:6362 | 142.111.227.167 (US) | 2026-02-19 | ✅ | ✅ |
| 02 | k19td4tu | Alexei Shon | alexeishon2@gmail.com | 104.232.209.101:6059 | 104.232.209.101 (US) | 2026-02-23 | ✅ | ✅ |
| 03 | k19td4uh | Jonathan Garcia Ramos | garciaramosjonathan8@gmail.com | 172.120.112.169:5848 | 172.120.112.169 (US) | 2026-02-20 | ✅ | ✅ |
| 04 | k19td4v5 | Yoshi Porfirio | yoshiporfirioyoshio@gmail.com | 104.168.118.139:6095 | 104.168.118.139 (US) | 2026-02-20 | ✅ | ✅ |
| 05 | k19td4vp | Hector Manuel Gutierrez Ramirez | gutierrezramirezhectormanuel6@gmail.com | 142.111.227.197:6392 | 142.111.227.197 (US) | 2026-02-21 | ✅ | ✅ |
| 06 | k19td4wc | Jonathan Martinez Medina | martinezmedinajonathan975@gmail.com | 149.57.17.162:5630 | 149.57.17.162 (US) | 2026-02-20 | ✅ | ✅ |
| 07 | k19td4x8 | Clara Sanchez Villela | clarasanchezvillela@gmail.com | 136.0.207.16:6593 | — | **Never opened** | ✅ | ✅ |
| 08 | k19td4xs | Alis Fleet | alisfleet@gmail.com | 69.58.12.159:8164 | — | 2026-02-23 | ✅ | ✅ |
| ~~09~~ | ~~k19td4yn~~ | ~~eljuande1965~~ | ~~eljuande1965@gmail.com~~ | ❌ DELETED | — | — | ❌ removed | ❌ removed |
| 10 | k19td50a | Oswaldin Lara | oswaldin.lara@gmail.com | 107.172.163.82:6598 | 107.172.163.82 (US) | 2026-03-01 | ✅ | ✅ |

### Findings
| Status | Item |
|--------|------|
| ❌→✅ | `k19td4yn` (slot 9) deleted from AdsPower — removed from JSON |
| ✅ | All 9 user_ids, emails, proxies, names match |
| ✅ | JSON now includes `full_name`, `proxy_host`, `proxy_port`, `phone` |

---

## Part 2 — `accounts.json` vs Supabase `adspower_profiles`

Fields verified: `slot`, `full_name`, `email`, `proxy_host:port`, `phone`

| Slot | user_id | slot ✓ | name ✓ | email ✓ | proxy ✓ | phone ✓ | Result |
|------|---------|--------|--------|---------|---------|---------|--------|
| 1 | k19td4st | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK |
| 2 | k19td4tu | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK |
| 3 | k19td4uh | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK |
| 4 | k19td4v5 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK |
| 5 | k19td4vp | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK |
| 6 | k19td4wc | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK |
| 7 | k19td4x8 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK |
| 8 | k19td4xs | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK |
| 10 | k19td50a | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ OK |

**OVERALL: ✅ ALL 9 PROFILES MATCH ON ALL FIELDS**

### Supabase state
| Field | Value |
|-------|-------|
| Rows | 9 (k19td4yn deleted) |
| `full_name` | populated on all 9 |
| `profile_name` | matches AdsPower format on all 9 |
| `cookie_status` | `active` on k19td50a only — `pending` on all others |
| `phone_number` | `+12068819903` on k19td50a — null on all others |

---

## Overall Result

| Source | Profiles | Clean |
|--------|----------|-------|
| AdsPower | 9 | ✅ |
| `accounts.json` | 9 | ✅ |
| Supabase `adspower_profiles` | 9 | ✅ |

**All 3 sources in sync. Same 9 profiles. Same order. Same data.**

---

## Actions Taken
1. ✅ AdsPower: `remark` written with full name on all 9 profiles
2. ✅ JSON: `k19td4yn` removed — enriched with `full_name`, `proxy_host`, `proxy_port`, `phone`
3. ✅ Supabase: `full_name` column added and populated
4. ✅ Supabase: `k19td4yn` deleted
5. ✅ Supabase: `profile_name` corrected on all rows
6. ✅ Supabase: `k19td50a` `cookie_status = active`
7. ✅ `proxies`: 16 stale `assigned_to` cleared, 1 orphan (`k19td4yn`) cleared → 9 assigned / 91 free
8. ✅ `gmail_accounts`: `eljuande1965` marked `retired`

---

## Expansion Plan — 10 New Profiles (slots 9, 11–19)

> Order: **Supabase → JSON → AdsPower**
> Proxy creds: `lehavxel / 4lzagcbkv7t9` · socks5 · US
> Password (all): `Simonala123`
> Skipping: `ochoachoaguillermomemo` (known browser crasher)

### New profiles

| Slot | user_id (TBD) | Full Name | Email | Proxy |
|------|--------------|-----------|-------|-------|
| 9  | TBD | Abraham Ibarra Padilla | abrahamibarrapadilla297@gmail.com | 104.168.8.82:5535 |
| 11 | TBD | Alejandra Lizzete | alejandralizzete@gmail.com | 104.238.37.230:6787 |
| 12 | TBD | Angel Ivan Lopez | angelivanlopez72@gmail.com | 104.253.48.154:5578 |
| 13 | TBD | Elluki Strike | ellukistrike@gmail.com | 107.172.221.31:5986 |
| 14 | TBD | Erick Sson | erickssson528@gmail.com | 107.173.137.205:6459 |
| 15 | TBD | FM Gutierrez | fmgutierrez123@gmail.com | 107.174.4.111:6080 |
| 16 | TBD | Jonathan Jonadidi | jonathanjonadidi@gmail.com | 136.0.118.93:6465 |
| 17 | TBD | Limon Rangel | limonrangel308@gmail.com | 136.0.126.242:6003 |
| 18 | TBD | Maria Conchita | mconchita521@gmail.com | 136.0.127.200:5909 |
| 19 | TBD | Gabriela Rodrigues Murillo | rodriguesmurillogabriela@gmail.com | 136.0.207.61:6638 |

> `user_id` values assigned by AdsPower on creation — update table after Step 3.

### Step 1 — Supabase
- [ ] INSERT 10 rows into `adspower_profiles` (slots 9, 11–19)
- [ ] Mark 10 emails as `in_use` in `gmail_accounts`
- [ ] Mark 10 proxies as `assigned_to` placeholder in `proxies`

### Step 2 — JSON (`config/accounts.json`)
- [ ] Append 10 entries (slot, user_id TBD, full_name, email, password, proxy_host, proxy_port, phone)

### Step 3 — AdsPower
- [ ] Create 10 profiles via API (`/api/v1/user/create`) in group `indeed` (8765960)
- [ ] Write `remark` (full name) for each
- [ ] Update Supabase + JSON with real `user_id` returned by AdsPower
