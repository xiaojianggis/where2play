import json
import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import requests

from utils import safe_get, sleep_polite

# -------------------------
# LIBCAL (Springshare)
# -------------------------
def _libcal_extract_calendar_id(html: str):
    # Matches: baseCalendarId: 13410 OR calendarId = 13410
    m = re.search(r"baseCalendarId\s*:\s*(\d+)", html)
    if m:
        return int(m.group(1))
    m = re.search(r"calendarId\s*=\s*(\d+)", html)
    if m:
        return int(m.group(1))
    return None

def scrape_libcal(calendar_url: str, perpage: int = 50, max_pages: int = 200):
    # 1) get HTML to find calendar id
    r = safe_get(calendar_url)
    r.raise_for_status()
    cal_id = _libcal_extract_calendar_id(r.text)
    if not cal_id:
        return []

    base = f"{urlparse(calendar_url).scheme}://{urlparse(calendar_url).netloc}"
    endpoint = f"{base}/ajax/calendar/list"

    events = []
    for page in range(1, max_pages + 1):
        params = {"c": cal_id, "date": "0000-00-00", "perpage": perpage, "page": page}
        jr = requests.get(endpoint, params=params, timeout=20)
        jr.raise_for_status()
        data = jr.json()
        rows = data.get("results", [])
        if not rows:
            break

        for e in rows:
            events.append({
                "platform": "libcal",
                "title": e.get("title"),
                "url": e.get("url"),
                "date_display": e.get("date"),
                "time_display": (e.get("start") or "") + (f"–{e.get('end')}" if e.get("end") else ""),
                "start": e.get("start"),
                "end": e.get("end"),
                "location_name": e.get("campus") or e.get("location"),
                "audience": [a.get("name") for a in e.get("audiences", []) if a.get("name")],
                "categories": [c.get("name") for c in e.get("categories_arr", []) if c.get("name")],
                "description": BeautifulSoup(e.get("shortdesc",""), "html.parser").get_text(" ", strip=True),
                "raw": e
            })
        sleep_polite(0.25)

    return events

# -------------------------
# LIBRARYCALENDAR (Drupal/Communico)
# Month/list pages -> daily feed URLs -> event URLs
# Event detail pages -> JSON-LD Event (best)
# -------------------------
def _parse_jsonld_event_detail(html: str, page_url: str):
    soup = BeautifulSoup(html, "html.parser")
    ld = soup.find("script", attrs={"type":"application/ld+json"})
    out = {"platform":"librarycalendar", "url": page_url}

    if ld and ld.string:
        try:
            data = json.loads(ld.string)
            if isinstance(data, dict) and data.get("@type") == "Event":
                out["title"] = data.get("name")
                out["description"] = BeautifulSoup(data.get("description",""), "html.parser").get_text(" ", strip=True)
                out["start"] = data.get("startDate")
                out["end"] = data.get("endDate")

                loc = data.get("location", {})
                addr = (loc.get("address") or {})
                out["location_name"] = loc.get("name")
                out["address"] = {
                    "street": addr.get("streetAddress"),
                    "city": addr.get("addressLocality"),
                    "state": addr.get("addressRegion"),
                    "zip": addr.get("postalCode"),
                    "country": addr.get("addressCountry"),
                }
        except Exception:
            pass

    # age groups in HTML
    aud = [a.get_text(strip=True) for a in soup.select(".lc-event__age-groups a")]
    if aud:
        out["audience"] = aud

    date_el = soup.select_one(".lc-event-info-item--date")
    time_el = soup.select_one(".lc-event-info-item--time")
    out["date_display"] = date_el.get_text(strip=True) if date_el else out.get("date_display")
    out["time_display"] = time_el.get_text(strip=True) if time_el else out.get("time_display")

    return out

def scrape_librarycalendar(calendar_root: str, horizon_days: int = 60, max_feeds: int = 90):
    """
    Universal approach:
    - hit /events/month or /events/upcoming if given
    - extract daily feed urls: /events/feed/html?...current_date=YYYY-MM-DD
    - parse each feed page for event links
    - fetch each event detail page -> JSON-LD
    """
    r = safe_get(calendar_root)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # print("r------------", r)

    feed_urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/events/feed/html" in href:
            feed_urls.add(urljoin(calendar_root, href))
    # print("feed_urls------------", feed_urls)


    # if month view didn't include feeds, try known views
    if not feed_urls:
        for guess in ["/events/month", "/events/upcoming", "/events/list"]:
            gr = safe_get(urljoin(calendar_root, guess))
            if gr.status_code >= 400:
                continue
            gsoup = BeautifulSoup(gr.text, "html.parser")
            for a in gsoup.find_all("a", href=True):
                href = a["href"]
                if "/events/feed/html" in href:
                    feed_urls.add(urljoin(calendar_root, href))
            if feed_urls:
                break

    feed_urls = list(feed_urls)[:max_feeds]

    event_urls = set()
    for fu in feed_urls:
        # print("This is for event detail page", fu)
        fr = safe_get(fu)
        if fr.status_code >= 400:
            continue
        fsoup = BeautifulSoup(fr.text, "html.parser")
        # find event links
        for a in fsoup.find_all("a", href=True):
            href = a["href"]
            if "/event/" in href:
                event_urls.add(urljoin(fu, href))
        sleep_polite(0.2)

    # print("event_urls is:=========", event_urls)

    # detail pages
    events = []
    for eu in list(event_urls):
        dr = safe_get(eu)
        # print(f"The dr -------- {eu} for the link of {dr}")
        if dr.status_code >= 400:
            continue
        events.append(_parse_jsonld_event_detail(dr.text, eu))
        sleep_polite(0.15)

    return events

# -------------------------
# WORDPRESS The Events Calendar (TEC)
# -------------------------
def scrape_wordpress_tec(site_url: str, per_page: int = 50, max_pages: int = 10):
    parsed = urlparse(site_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    api = f"{base}/wp-json/tribe/events/v1/events"

    events = []
    page = 1
    while page <= max_pages:
        params = {"per_page": per_page, "page": page}
        r = requests.get(api, params=params, timeout=20)
        if r.status_code != 200:
            break
        data = r.json()
        rows = data.get("events", [])
        if not rows:
            break
        for e in rows:
            events.append({
                "platform": "wordpress_tec",
                "title": e.get("title"),
                "url": e.get("url"),
                "start": e.get("start_date"),
                "end": e.get("end_date"),
                "description": BeautifulSoup(e.get("description",""), "html.parser").get_text(" ", strip=True),
                "location_name": (e.get("venue") or {}).get("venue"),
                "address": (e.get("venue") or {}).get("address"),
                "categories": [c.get("name") for c in e.get("categories", []) if c.get("name")],
                "audience": [],
                "raw": e
            })
        page += 1
        sleep_polite(0.2)

    return events

# -------------------------
# GENERIC HTML fallback (best effort)
# -------------------------
def scrape_generic_html(events_url: str, max_events: int = 200):
    r = safe_get(events_url)
    if r.status_code >= 400:
        return []
    soup = BeautifulSoup(r.text, "html.parser")

    out = []
    KEYWORDS = ["event", "events", "program", "story", "workshop", "calendar"]
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        if len(text) < 6:
            continue
        url = urljoin(events_url, a["href"])
        if any(x in url.lower() for x in ["feed", "rss", "ical", "export"]):
            continue
        if any(k in text.lower() for k in KEYWORDS):
            out.append({
                "platform": "generic_html",
                "title": text[:140],
                "url": url,
                "start": None, "end": None,
                "description": None,
                "location_name": None,
                "address": None,
                "audience": [],
                "categories": [],
            })
        if len(out) >= max_events:
            break
    return out