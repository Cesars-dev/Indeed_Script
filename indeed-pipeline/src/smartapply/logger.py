"""
Non-blocking Supabase logger — fire and forget.
Never blocks the pipeline. If the POST fails, it silently drops.
"""
import asyncio
import os
import json as _json


def _get_headers():
    key = os.getenv("SUPABASE_KEY", "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def _post(table: str, data: dict):
    """POST to Supabase REST API. Non-blocking, fire-and-forget."""
    sb_url = os.getenv("SUPABASE_URL", "")
    if not sb_url:
        return
    headers = _get_headers()
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{sb_url}/rest/v1/{table}",
                json=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            )
    except ImportError:
        # aiohttp not installed — fall back to requests in thread
        import requests
        try:
            requests.post(
                f"{sb_url}/rest/v1/{table}",
                json=data,
                headers=headers,
                timeout=5,
            )
        except Exception:
            pass
    except Exception:
        pass  # fire and forget — never crash the pipeline


def log(table: str, data: dict):
    """Fire-and-forget log to Supabase. Returns immediately."""
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_post(table, data))
    except RuntimeError:
        pass  # no event loop — skip silently


