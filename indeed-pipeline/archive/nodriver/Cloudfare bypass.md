<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# what if we encounter cloudfare... is there a way to by pass it?

Great timing to nail this down. The good news: **your AdsPower setup already handles ~80% of Cloudflare cases passively**. Here's the full picture.

***

## How Cloudflare Hits Indeed (4 Challenge Types)

| Type | What triggers it | How hard |
| :-- | :-- | :-- |
| **JS Challenge** ("Just a moment…") | Cold/unknown IP | ✅ Auto-resolved by warm `cf_clearance` cookie |
| **Turnstile (invisible)** | Suspicious behavior | ✅ nodriver passes silently |
| **Turnstile (interactive)** | Fresh profile, new IP | 🟡 Needs `nodriver-cf-bypass` plugin |
| **Bot Management ML** | Pattern detection | 🔴 Needs behavioral tricks + proxy quality |


***

## Why You're Already Mostly Safe

AdsPower warm profiles store the `cf_clearance` cookie from prior Indeed visits.  Cloudflare reads that cookie on entry and skips the challenge entirely — no JS challenge fires. This is your first and strongest layer.[^1]

nodriver itself is the \#1 recommended tool for Cloudflare bypass in 2026 — it avoids injecting `navigator.webdriver`, connects via CDP without automation flags, and is specifically cited over Selenium/Puppeteer.[^2]

***

## The Full Defense Stack

### Layer 1 — Detect \& wait (always required)

```python
async def handle_cloudflare(tab, timeout: int = 20) -> bool:
    """
    Detect all CF challenge types and wait them out.
    Returns True if cleared, raises on timeout.
    """
    import time
    start = time.time()

    CF_TITLES = ["just a moment", "attention required", "checking your browser"]
    CF_CODES  = ["error code: 1020", "error code: 1015", "cf-error"]

    while time.time() - start < timeout:
        title   = (await tab.evaluate("document.title")).lower()
        content = (await tab.get_content()).lower()
        url     = tab.url

        is_cf_challenge = (
            any(t in title for t in CF_TITLES) or
            any(c in content for c in CF_CODES) or
            "__cf_chl" in url
        )

        if is_cf_challenge:
            print(f"  ⚠️  Cloudflare detected (title: '{title}') — waiting...")
            await asyncio.sleep(3)
        else:
            return True  # clean page

    raise Exception(f"Cloudflare challenge did not resolve within {timeout}s")
```


***

### Layer 2 — `nodriver-cf-bypass` for Turnstile (drop-in plugin)

This is a dedicated nodriver plugin that finds the Turnstile iframe, simulates the click, and retries automatically.[^3]

```bash
pip install nodriver-cf-bypass
```

```python
from nodriver_cf_bypass import CFBypass

async def apply_to_job(apply_url: str, docx_path, user_id: str) -> dict:
    browser = await start_adspower_browser(user_id)
    tab = await browser.get(apply_url, new_tab=True)
    await tab  # wait for initial load

    # Auto-detect and solve Turnstile if present
    cf = CFBypass(_browser_tab=tab, _debug=False)
    solved = await cf.bypass(
        _max_retries=10,
        _interval_between_retries=2,
        _reload_page_after_n_retries=3
    )

    if not solved:
        return {"status": "failed", "reason": "cloudflare_unsolved"}

    # Now safe to proceed
    await handle_cloudflare(tab)   # belt + suspenders check
    await human_scroll(tab)
    ...
```


***

### Layer 3 — FlareSolverr on VPS (fallback for hard blocks)

This is a Docker service that handles the challenge in a real browser and returns you the `cf_clearance` cookie. You then inject it into your AdsPower session.[^4]

```bash
# On VPS — run the nodriver-enhanced image (better than official)
docker run -d \
  --name flaresolverr \
  --restart unless-stopped \
  -p 127.0.0.1:8191:8191 \
  ghcr.io/svaningelgem/flaresolverr:latest
```

```python
import requests

def get_cf_clearance_via_flaresolverr(url: str) -> str:
    """Use FlareSolverr to solve challenge — returns cf_clearance value"""
    r = requests.post("http://localhost:8191/v1", json={
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 60000
    })
    data = r.json()
    cookies = data["solution"]["cookies"]
    cf_cookie = next((c for c in cookies if c["name"] == "cf_clearance"), None)
    return cf_cookie["value"] if cf_cookie else None
```

Then inject it into the running AdsPower tab via CDP:

```python
async def inject_cf_cookie(tab, cf_value: str):
    await tab.send(
        "Network.setCookie",
        name="cf_clearance",
        value=cf_value,
        domain=".indeed.com",
        path="/",
        secure=True
    )
    await tab.reload()
```


***

### Layer 4 — CapSolver for interactive Turnstile (last resort, paid)

If Turnstile shows a "I'm not a robot" checkbox that requires human action:[^5]

```python
import capsolver

capsolver.api_key = os.getenv("CAPSOLVER_KEY")  # ~$0.001/solve

async def solve_turnstile(tab) -> bool:
    """Detect Turnstile widget, solve via CapSolver API"""
    # Find sitekey from page
    sitekey = await tab.evaluate("""
        (() => {
            const el = document.querySelector('[data-sitekey]');
            return el ? el.getAttribute('data-sitekey') : null;
        })()
    """)
    if not sitekey:
        return True  # no Turnstile present

    solution = capsolver.solve({
        "type": "AntiTurnstileTaskProxyLess",
        "websiteURL": tab.url,
        "websiteKey": sitekey
    })
    token = solution["token"]

    # Inject token into page
    await tab.evaluate(f"""
        document.querySelector('[name="cf-turnstile-response"]').value = '{token}';
    """)
    return True
```


***

## What to plug into `nodriver_indeed.py`

```python
async def apply_to_job(apply_url: str, docx_path, user_id: str) -> dict:
    browser = await start_adspower_browser(user_id)
    tab = await browser.get(apply_url, new_tab=True)
    await tab

    # ── Cloudflare gauntlet ──────────────────────────────────
    try:
        # Layer 2: Turnstile plugin
        cf = CFBypass(_browser_tab=tab, _debug=False)
        await cf.bypass(_max_retries=8, _interval_between_retries=2)

        # Layer 1: JS challenge wait
        await handle_cloudflare(tab, timeout=25)

    except Exception as e:
        return {"status": "failed", "reason": f"cloudflare: {e}"}
    # ────────────────────────────────────────────────────────

    await human_scroll(tab)
    # ... rest of Indeed apply logic
```


***

## Reality Check for Indeed Specifically

Indeed runs **Cloudflare Bot Management** (enterprise tier), not just the free plan.  That means it uses ML behavioral analysis — but the critical point is:[^2]

- A warm AdsPower profile with **existing Indeed cookies + `cf_clearance`** → almost certainly no challenge fires at all
- The challenge only appears on **first visit per profile** or after **long inactivity**
- Solution: Before running the apply batch, warm up each profile by visiting Indeed once and letting it sit for 30 seconds

```python
async def warm_profile(user_id: str):
    """Pre-warm Indeed session before apply batch"""
    browser = await start_adspower_browser(user_id)
    tab = await browser.get("https://www.indeed.com", new_tab=True)
    await asyncio.sleep(random.uniform(20, 35))  # let CF cookie bake
    await tab.close()
    print(f"  ✅ Profile {user_id} warmed")
```

Run this for all 10 profiles before starting the apply loop and you'll rarely see a Cloudflare challenge mid-apply.
<span style="display:none">[^10][^11][^12][^13][^14][^15][^6][^7][^8][^9]</span>

<div align="center">⁂</div>

[^1]: https://www.reddit.com/r/webscraping/comments/1ncescp/bypassing_cloudflare_turnstile/

[^2]: https://scrapfly.io/blog/posts/how-to-bypass-cloudflare-anti-scraping

[^3]: https://github.com/KlozetLabs/nodriver-cf-bypass

[^4]: https://github.com/FlareSolverr/FlareSolverr/discussions/1416

[^5]: https://www.capsolver.com/es/blog/web-scraping/bypass-cloudflare-challenge-2025

[^6]: https://sites.google.com/view/mikes-tech-notes/5-working-methods-to-bypass-cloudflare-in-2025

[^7]: https://github.com/topics/nodriver

[^8]: https://roundproxies.com/blog/bypass-cloudflare/

[^9]: https://brightdata.com/blog/web-data/bypass-cloudflare

[^10]: https://flaresolverr.com/flaresolverr-integration-with-python-node-fails/

[^11]: https://www.reddit.com/r/webscraping/comments/1g40qy2/i_made_a_cloudflarebypass/

[^12]: https://scrape.do/blog/bypass-cloudflare/

[^13]: https://flaresolverr.com/complete-flaresolverr-tutorial-setup-integration/

[^14]: https://www.youtube.com/watch?v=We_5Hq4K4-M

[^15]: https://brightdata.com/blog/web-data/flaresolverr-bypass-cloudflare

