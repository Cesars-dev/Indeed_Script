"""
reCAPTCHA v2 solver using 2Captcha API.

Flow:
  1. Detect reCAPTCHA on page (div.g-recaptcha or iframe[src*="recaptcha"])
  2. Extract sitekey
  3. Send to 2Captcha → poll for response token
  4. Inject token + fire callback
  5. Verify form accepted it (submit button enabled)
"""
import asyncio
import os
import httpx

_API_KEY = os.getenv("TWOCAPTCHA_API_KEY", "")
_IN_URL = "https://2captcha.com/in.php"
_RES_URL = "https://2captcha.com/res.php"


async def _get_token(sitekey: str, page_url: str) -> str | None:
    """Send reCAPTCHA to 2Captcha, poll for result, return token."""
    key = _API_KEY or os.getenv("TWOCAPTCHA_API_KEY", "")
    if not key:
        print("  [reCAPTCHA] TWOCAPTCHA_API_KEY not set")
        return None

    async with httpx.AsyncClient(timeout=120) as client:
        # Submit task
        r = await client.get(_IN_URL, params={
            "key": key,
            "method": "userrecaptcha",
            "googlekey": sitekey,
            "pageurl": page_url,
            "json": "1",
        })
        data = r.json()
        if data.get("status") != 1:
            print(f"  [reCAPTCHA] Submit failed: {data.get('request', data)}")
            return None

        task_id = data["request"]
        print(f"  [reCAPTCHA] Task submitted: {task_id} — polling...")

        # Poll for result (2Captcha recommends 5s intervals, first check at 15s)
        await asyncio.sleep(12)
        for i in range(24):  # max ~2 min
            r = await client.get(_RES_URL, params={
                "key": key,
                "action": "get",
                "id": task_id,
                "json": "1",
            })
            data = r.json()
            if data.get("status") == 1:
                token = data["request"]
                print(f"  [reCAPTCHA] Solved in ~{12 + (i+1)*5}s ✓")
                return token
            if data.get("request") not in ("CAPCHA_NOT_READY",):
                print(f"  [reCAPTCHA] Error: {data.get('request', data)}")
                return None
            await asyncio.sleep(5)

    print("  [reCAPTCHA] Timeout (2 min)")
    return None


async def has_recaptcha(page) -> bool:
    """Check if page has a reCAPTCHA v2 widget."""
    return await page.evaluate("""() =>
        !!document.querySelector('.g-recaptcha, iframe[src*="recaptcha"], [data-sitekey]')
    """)


async def solve_recaptcha(page) -> bool:
    """
    Full reCAPTCHA v2 solve: detect → extract sitekey → solve via 2Captcha → inject token.
    Returns True if the form accepted the solution.
    """
    # ── 1. Scroll to bottom to ensure reCAPTCHA widget is loaded ────────────
    try:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)
    except Exception:
        pass

    # ── 2. Extract sitekey ──────────────────────────────────────────────────
    sitekey = await page.evaluate("""() => {
        // Method 1: data-sitekey attribute
        const div = document.querySelector('.g-recaptcha[data-sitekey], [data-sitekey]');
        if (div) return div.getAttribute('data-sitekey');

        // Method 2: reCAPTCHA iframe src parameter
        const iframe = document.querySelector('iframe[src*="recaptcha"]');
        if (iframe) {
            const m = iframe.src.match(/[?&]k=([^&]+)/);
            if (m) return m[1];
        }

        // Method 3: inline script
        for (const s of document.querySelectorAll('script')) {
            const m = s.textContent.match(/sitekey['\"\\s:]+['\"]([0-9A-Za-z_\\-]{40})['"]/);
            if (m) return m[1];
        }
        return null;
    }""")

    if not sitekey:
        print("  [reCAPTCHA] No sitekey found on page")
        return False

    print(f"  [reCAPTCHA] sitekey={sitekey[:20]}...")

    # ── 3. Get token from 2Captcha ──────────────────────────────────────────
    token = await _get_token(sitekey, page.url)
    if not token:
        return False

    # ── 4. Inject token + fire callback ─────────────────────────────────────
    await page.evaluate("""(token) => {
        // Set hidden textarea with native setter (React/Angular safe)
        const ta = document.getElementById('g-recaptcha-response');
        if (ta) {
            const setter = Object.getOwnPropertyDescriptor(
                HTMLTextAreaElement.prototype, 'value'
            ).set;
            setter.call(ta, token);
            ta.style.display = 'block';
            ta.dispatchEvent(new Event('input',  { bubbles: true }));
            ta.dispatchEvent(new Event('change', { bubbles: true }));
        }

        // Also set any other response textareas (some pages have multiple)
        document.querySelectorAll('[id^="g-recaptcha-response"]').forEach(el => {
            if (el !== ta) {
                const s = Object.getOwnPropertyDescriptor(
                    HTMLTextAreaElement.prototype, 'value'
                ).set;
                s.call(el, token);
                el.dispatchEvent(new Event('input',  { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });

        // Fire named data-callback
        const div = document.querySelector('.g-recaptcha[data-callback], [data-callback]');
        if (div) {
            const cbName = div.getAttribute('data-callback');
            if (typeof window[cbName] === 'function') {
                window[cbName](token);
                return;
            }
        }

        // Walk ___grecaptcha_cfg.clients for callback
        try {
            const walk = (obj) => {
                if (!obj || typeof obj !== 'object') return;
                if (typeof obj.callback === 'function') { obj.callback(token); return; }
                Object.values(obj).forEach(walk);
            };
            Object.values(window.___grecaptcha_cfg?.clients || {}).forEach(walk);
        } catch (e) { console.warn('callback walk failed', e); }
    }""", token)

    await asyncio.sleep(2)  # let form state settle

    # ── 5. Verify acceptance ────────────────────────────────────────────────
    accepted = await page.evaluate("""() => {
        // Check grecaptcha.getResponse()
        try {
            if (typeof grecaptcha !== 'undefined' && grecaptcha.getResponse().length > 0) return true;
        } catch(e) {}
        try {
            if (typeof grecaptcha !== 'undefined' && grecaptcha.enterprise &&
                grecaptcha.enterprise.getResponse().length > 0) return true;
        } catch(e) {}

        // Check if submit button is now enabled
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            if (b.textContent.toLowerCase().includes('submit') && !b.disabled) return true;
        }
        return false;
    }""")

    print(f"  [reCAPTCHA] {'✅ Accepted — submit should be enabled' if accepted else '❌ Not accepted'}")
    return accepted
