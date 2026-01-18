import time
import random
import requests

BASE = "https://stats.nba.com/stats"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

def nba_get(endpoint: str, params: dict, *, timeout=90, retries=5):
    """
    NBA stats endpoints can be flaky / slow. This does:
    - longer timeout
    - retry with exponential backoff + jitter
    """
    url = f"{BASE}/{endpoint}"
    last_err = None

    with requests.Session() as s:
        s.headers.update(HEADERS)

        for attempt in range(1, retries + 1):
            try:
                r = s.get(url, params=params, timeout=timeout)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_err = e
                sleep_s = (2 ** (attempt - 1)) + random.random()
                print(f"[nba_get] attempt {attempt}/{retries} failed: {type(e).__name__}. sleeping {sleep_s:.1f}s")
                time.sleep(sleep_s)

    raise last_err
