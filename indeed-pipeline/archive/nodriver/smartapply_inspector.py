#!/usr/bin/env python3
"""
smartapply_inspector.py — Passive DOM observer.

Attaches to AdsPower profile and watches passively while the USER navigates.
On every URL change (and every 8s): dumps full DOM summary + saves screenshot.
Does NOT click anything.

Usage:
  python scripts/smartapply_inspector.py

Press Ctrl+C to stop.
Output: /tmp/inspector_<profile>_<ts>/   (screenshots + JSON DOM dumps)
"""
import asyncio
import json
import os
import sys
import time

import requests
import nodriver as uc

ADSPOWER_BASE = "http://localhost:50325"
ADSPOWER_API_KEY = "6690380481d7de70c40230dca72e9403005bda7f364e3e6f"
PROFILE_ID = "k19td4vp"  # gutierrezramirezhectormanuel6@gmail.com
DEBUG_DIR = f"/tmp/inspector_{PROFILE_ID}_{int(time.time())}"

# Full DOM extraction — runs in browser context
DOM_EXTRACT_JS = """
(() => {
    const txt = el => (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 150);

    // Page headings
    const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4'))
        .map(h => `[${h.tagName}] ${txt(h)}`).filter(s => s.length > 3);

    // Progress bar
    const pb = document.querySelector('[role="progressbar"], progress, [aria-valuenow]');
    const progress = pb
        ? (pb.getAttribute('aria-valuenow') || pb.getAttribute('value') || pb.value || '?') + '%'
        : null;

    // All visible buttons
    const buttons = Array.from(
            document.querySelectorAll('button, [role="button"], input[type="submit"], a[class*="button"]')
        )
        .filter(b => b.offsetParent !== null)
        .map(b => ({ text: txt(b), type: b.type || b.tagName, id: b.id || null }))
        .filter(b => b.text.length > 0);

    // Text inputs + textareas with their labels
    const inputs = Array.from(document.querySelectorAll('input, textarea'))
        .filter(i => i.offsetParent !== null && i.type !== 'hidden' && i.type !== 'file')
        .map(i => {
            const lbl = document.querySelector('label[for="' + i.id + '"]');
            const label = lbl ? txt(lbl)
                : (i.placeholder || i.getAttribute('aria-label') || i.name || i.type || '?');
            return { type: i.type, id: i.id || null, label, value: i.value || '' };
        });

    // File inputs (resume upload)
    const fileInputs = Array.from(document.querySelectorAll('input[type="file"]'))
        .map(i => ({ id: i.id || null, accept: i.accept || '*', name: i.name || null }));

    // Select dropdowns with options
    const selects = Array.from(document.querySelectorAll('select'))
        .filter(s => s.offsetParent !== null)
        .map(s => {
            const lbl = document.querySelector('label[for="' + s.id + '"]');
            const label = lbl ? txt(lbl) : (s.getAttribute('aria-label') || s.name || '?');
            const opts = Array.from(s.options).map(o => ({ value: o.value, text: o.text.trim() }));
            return { label, id: s.id || null, selected: s.value, options: opts };
        });

    // Radio groups
    const radioGroups = {};
    document.querySelectorAll('input[type="radio"]').forEach(r => {
        if (!radioGroups[r.name]) radioGroups[r.name] = [];
        const lbl = document.querySelector('label[for="' + r.id + '"]');
        radioGroups[r.name].push({
            value: r.value,
            label: lbl ? txt(lbl) : r.value,
            checked: r.checked,
        });
    });

    // Checkboxes
    const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'))
        .filter(c => c.offsetParent !== null)
        .map(c => {
            const lbl = document.querySelector('label[for="' + c.id + '"]');
            return { label: lbl ? txt(lbl) : c.name, checked: c.checked };
        });

    // Key visible paragraphs / question text
    const paras = Array.from(
            document.querySelectorAll('p, li, [class*="question"], [class*="label"], legend, fieldset > div')
        )
        .filter(el => el.offsetParent !== null)
        .map(txt)
        .filter(s => s.length > 8 && s.length < 300)
        .slice(0, 15);

    // Form action (where does submit go?)
    const forms = Array.from(document.querySelectorAll('form'))
        .map(f => ({ action: f.action, method: f.method }));

    return {
        title: document.title,
        headings,
        progress,
        buttons,
        inputs,
        fileInputs,
        selects,
        radioGroups,
        checkboxes,
        paras,
        forms,
    };
})()
"""


def _start_profile(user_id: str) -> dict:
    resp = requests.get(
        f"{ADSPOWER_BASE}/api/v1/browser/start",
        params={"user_id": user_id, "api_key": ADSPOWER_API_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"AdsPower start failed: {data}")
    return data["data"]


def _stop_profile(user_id: str):
    try:
        requests.get(
            f"{ADSPOWER_BASE}/api/v1/browser/stop",
            params={"user_id": user_id, "api_key": ADSPOWER_API_KEY},
            timeout=10,
        )
    except Exception:
        pass


def _print_dom(label: str, dom: dict, url: str):
    SEP = "─" * 60
    print(f"\n{SEP}")
    print(f"  [{label}]")
    print(f"  URL  : {url}")
    print(f"  Title: {dom.get('title', '?')}")
    print(f"{SEP}")

    if dom.get("progress"):
        print(f"  ▓ Progress: {dom['progress']}")

    if dom.get("headings"):
        print(f"\n  Headings:")
        for h in dom["headings"]:
            print(f"    {h}")

    if dom.get("buttons"):
        print(f"\n  Buttons:")
        for b in dom["buttons"]:
            id_str = f" [#{b['id']}]" if b.get("id") else ""
            print(f"    '{b['text']}'{id_str}")

    if dom.get("fileInputs"):
        print(f"\n  File inputs (resume upload):")
        for fi in dom["fileInputs"]:
            print(f"    input[file] id={fi['id']} accept={fi['accept']}")

    if dom.get("inputs"):
        print(f"\n  Text inputs:")
        for inp in dom["inputs"]:
            filled = f" = '{inp['value']}'" if inp["value"] else " (empty)"
            id_str = f" [#{inp['id']}]" if inp.get("id") else ""
            print(f"    [{inp['type']}]{id_str} {inp['label']}{filled}")

    if dom.get("selects"):
        print(f"\n  Dropdowns:")
        for sel in dom["selects"]:
            opts_str = ", ".join(f"'{o['text']}'" for o in sel["options"][:6])
            print(f"    {sel['label']} (selected='{sel['selected']}')")
            print(f"      opts: [{opts_str}{'...' if len(sel['options']) > 6 else ''}]")

    if dom.get("radioGroups"):
        print(f"\n  Radio groups:")
        for name, opts in dom["radioGroups"].items():
            checked = next((o["label"] for o in opts if o["checked"]), "none")
            labels = [o["label"] for o in opts]
            print(f"    '{name}': {labels}  →  checked='{checked}'")

    if dom.get("checkboxes"):
        print(f"\n  Checkboxes:")
        for cb in dom["checkboxes"]:
            state = "☑" if cb["checked"] else "☐"
            print(f"    {state} {cb['label']}")

    if dom.get("paras"):
        print(f"\n  Key text on page:")
        for p in dom["paras"]:
            print(f"    · {p}")

    print(f"{SEP}")


async def _get_active_tab(browser) -> uc.Tab:
    """Use the most recently active tab (highest index that's not blank)."""
    tabs = browser.tabs
    for tab in reversed(tabs):
        try:
            url = tab.url
            if url and url not in ("", "about:blank", "chrome://newtab/"):
                return tab
        except Exception:
            continue
    return tabs[-1] if tabs else None


async def main():
    os.makedirs(DEBUG_DIR, exist_ok=True)
    print("=" * 60)
    print("SmartApply Inspector — PASSIVE observer (never clicks)")
    print(f"Profile : {PROFILE_ID}")
    print(f"Output  : {DEBUG_DIR}/")
    print("=" * 60)
    print("\nStarting AdsPower profile...")

    profile_data = _start_profile(PROFILE_ID)
    debug_port = int(profile_data["debug_port"])
    print(f"debug_port: {debug_port}")
    print("Attaching nodriver...")

    try:
        browser = await uc.Browser.create(host="127.0.0.1", port=debug_port)
        print("\n✓ Attached. Navigate in the browser — I'm watching every step.")
        print("  Screenshots + DOM dumps saved automatically on each URL change.")
        print("  Ctrl+C to stop.\n")

        last_url = None
        screenshot_idx = 0
        last_snapshot_time = 0

        while True:
            await asyncio.sleep(1.5)

            try:
                # Track whichever tab is active
                page = await _get_active_tab(browser)
                if not page:
                    continue

                url = page.url
                now = time.time()
                url_changed = (url != last_url)
                periodic = (now - last_snapshot_time) > 10  # snapshot every 10s too

                if url_changed or periodic:
                    try:
                        dom = await page.evaluate(DOM_EXTRACT_JS)
                    except Exception as e:
                        dom = {"title": "?", "error": str(e)}
                        print(f"  [dom eval error] {e}")

                    if url_changed:
                        label = f"URL_CHANGE_{screenshot_idx:03d}"
                        print(f"\n>>> URL CHANGED: {url}")
                    else:
                        label = f"periodic_{screenshot_idx:03d}"

                    # Screenshot
                    png_path = os.path.join(DEBUG_DIR, f"{label}.png")
                    try:
                        await page.save_screenshot(png_path)
                    except Exception as e:
                        print(f"  [screenshot error] {e}")

                    # Print DOM to console
                    _print_dom(label, dom, url)

                    # Save DOM to JSON for later analysis
                    json_path = os.path.join(DEBUG_DIR, f"{label}.json")
                    with open(json_path, "w") as f:
                        json.dump({"url": url, "dom": dom}, f, indent=2, default=str)

                    last_url = url
                    last_snapshot_time = now
                    screenshot_idx += 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"  [poll error] {e}")

    except KeyboardInterrupt:
        pass
    finally:
        print(f"\n\nStopped. All data in:\n  {DEBUG_DIR}/")
        print(f"  {screenshot_idx} snapshots captured.")
        _stop_profile(PROFILE_ID)
        print("Profile stopped.")


if __name__ == "__main__":
    asyncio.run(main())
