import os
import requests
from dotenv import load_dotenv

load_dotenv()

WEBSHARE_API_KEY = os.getenv("WEBSHARE_API_KEY")

_proxy_cache = None


def fetch_proxies():
    proxies = []
    page = 1
    while True:
        r = requests.get(
            "https://proxy.webshare.io/api/v2/proxy/list/",
            params={"mode": "direct", "page": page, "page_size": 100},
            headers={"Authorization": f"Token {WEBSHARE_API_KEY}"},
            timeout=15
        )
        data = r.json()
        results = data.get("results", [])
        proxies.extend(results)
        if not data.get("next"):
            break
        page += 1
    return proxies


def get_proxy(index: int) -> str:
    global _proxy_cache
    if _proxy_cache is None:
        _proxy_cache = fetch_proxies()
    p = _proxy_cache[index % len(_proxy_cache)]
    return f"http://{p['username']}:{p['password']}@{p['proxy_address']}:{p['port']}"


if __name__ == "__main__":
    proxies = fetch_proxies()
    print(f"Fetched {len(proxies)} proxies")
    for p in proxies[:5]:
        print(f"  {p['proxy_address']}:{p['port']} ({p['city_name']}, {p['country_code']})")
