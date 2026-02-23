import re
import time
import json
import hashlib
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def safe_get(url: str, timeout: int = 20) -> requests.Response:
    r = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout, allow_redirects=True)
    return r

def is_url_reachable(url: str, timeout: int = 15) -> bool:
    # HEAD is unreliable; do GET with browser headers.
    try:
        r = safe_get(url, timeout=timeout)
        return r.status_code < 400
    except requests.RequestException:
        return False

def extract_links(html: str, base_url: str, max_links: int = 200):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)[:120]
        href = a["href"].strip()
        full = urljoin(base_url, href)
        if not full.startswith("http"):
            continue
        links.append({"text": text, "href": full})
        if len(links) >= max_links:
            break
    return links

def normalize_event(obj: dict) -> dict:
    # A single schema for all platforms
    return {
        "library_name": obj.get("library_name"),
        "library_website": obj.get("library_website"),
        "platform": obj.get("platform"),
        "title": obj.get("title"),
        "url": obj.get("url"),
        "start": obj.get("start"),
        "end": obj.get("end"),
        "date_display": obj.get("date_display"),
        "time_display": obj.get("time_display"),
        "location_name": obj.get("location_name"),
        "address": obj.get("address"),  # dict or None
        "audience": obj.get("audience", []),
        "categories": obj.get("categories", []),
        "description": obj.get("description"),
        "raw": obj.get("raw")  # optional
    }

def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]

def sleep_polite(seconds=0.3):
    time.sleep(seconds)

def ensure_dir(path: str):
    import os
    os.makedirs(path, exist_ok=True)


