import requests
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://libwww.freelibrary.org"
# BASE = "https://www.upperdublinlibrary.org"
BASE = "https://www.allentownpl.org"

START_PAGE = 1
END_PAGE = 114  # confirmed from pagination

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://libwww.freelibrary.org/calendar/",
    "Connection": "keep-alive",
}

session = requests.Session()
session.headers.update(HEADERS)


def bootstrap_session():
    """
    REQUIRED: establish cookies by visiting calendar landing page first
    """
    r = session.get(BASE + "/calendar/", timeout=60)
    r.raise_for_status()
    print("✅ Session bootstrapped (cookies set)")


def parse_event_block(block):
    title_el = block.select_one("h3 a[href^='/calendar/event/']")
    if not title_el:
        return None

    title = title_el.get_text(strip=True)
    url = urljoin(BASE, title_el["href"])

    date_str = block.select_one("strong").get_text(strip=True)
    time_el = block.select_one("span.text-lowercase")
    time_str = time_el.get_text(strip=True) if time_el else None

    loc_el = block.select_one('a[href^="/locations/"]')
    location = loc_el.get_text(strip=True) if loc_el else None

    desc_el = block.select_one("p:nth-of-type(2)")
    description = desc_el.get_text(" ", strip=True) if desc_el else None

    ages = [a.get_text(strip=True) for a in block.select('a[href^="/calendar/age/"]')]
    types = [a.get_text(strip=True) for a in block.select('a[href^="/calendar/type/"]')]
    series = [a.get_text(strip=True) for a in block.select('a[href^="/calendar/series/"]')]
    tags = [a.get_text(strip=True) for a in block.select('a[href^="/calendar/tag/"]')]

    return {
        "title": title,
        "date": date_str,
        "time": time_str,
        "location": location,
        "url": url,
        "description": description,
        "ages": ages,
        "types": types,
        "series": series,
        "tags": tags,
        "source": "Free Library of Philadelphia"
    }


def scrape_page(page):
    url = f"{BASE}/calendar/main/home/page/{page}/having/all"
    r = session.get(url, timeout=60)

    if r.status_code == 403:
        raise RuntimeError(
            f"403 Forbidden on page {page}. "
            "Session cookies missing or blocked."
        )

    soup = BeautifulSoup(r.text, "html.parser")
    events = []

    for block in soup.select("div.row.margin-bottom-5"):
        event = parse_event_block(block)
        if event:
            events.append(event)

    return events


def scrape_all_events():
    bootstrap_session()
    
    all_events = []

    for page in range(START_PAGE, END_PAGE + 1):
        print(f"Scraping page {page}")
        events = scrape_page(page)
        print(f"  → {len(events)} events")
        all_events.extend(events)
        time.sleep(1)  # important: do NOT go faster

    return all_events


if __name__ == "__main__":
    events = scrape_all_events()

    with open("data/phila_freelibrary_events_all.json", "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(events)} events to phila_freelibrary_events_all.json")