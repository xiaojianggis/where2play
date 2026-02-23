import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import json
import time
import re
import time
from playwright.sync_api import sync_playwright


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def find_upcoming_events_link(homepage_url):
    '''
    This function will find the link to the upcoming events, like a libray url address 
    "https://ccmellorlibrary.org/"

    Through this function, we are able to find the link to the upcoming events
    https://ccmellor.librarycalendar.com/

    Calling example,
        library_url = "https://ccmellorlibrary.org/"
        result = find_upcoming_events_link(library_url)
        upcoming_events = result['url']
        print(result['url'])
    '''

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }
    
    KEYWORDS = [
        "event",
        "events",
        "calendar",
        "program",
        "programs",
        "upcoming"
    ]

    try:
        r = requests.get(homepage_url, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if r.status_code == 403:
            print(f"⚠️ 403 Forbidden for {homepage_url}, retrying without Referer")
            HEADERS.pop("Referer", None)
            r = requests.get(homepage_url, headers=HEADERS, timeout=30)
        else:
            raise

    soup = BeautifulSoup(r.text, "html.parser")

    candidates = []

    for a in soup.find_all("a", href=True):
        text = (a.get_text(strip=True) or "").lower()
        href = a["href"].strip()
        full_url = urljoin(homepage_url, href)

        score = 0
        reasons = []

        # 1️⃣ Text intent
        if any(k in text for k in KEYWORDS):
            score += 4
            reasons.append("keyword_in_text")

        # 2️⃣ URL intent
        if any(k in full_url.lower() for k in ["calendar", "events", "libcal"]):
            score += 3
            reasons.append("keyword_in_url")

        # 3️⃣ Button / CTA styling
        classes = " ".join(a.get("class", [])).lower()
        if any(c in classes for c in ["button", "btn"]):
            score += 2
            reasons.append("button_style")

        # 4️⃣ External calendar platform
        if "libcal.com" in full_url:
            score += 5
            reasons.append("libcal")

        if score > 0:
            candidates.append({
                "text": a.get_text(strip=True),
                "url": full_url,
                "score": score,
                "reasons": reasons
            })

    if not candidates:
        return None

    # highest score wins
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[0]


def scrape_freelibrary_json(location_code):
    """
    Official Free Library of Philadelphia JSON feed
    """
    url = f"https://libwww.freelibrary.org/calendar/json?location_code={location_code}"

    r = requests.get(url, timeout=20)
    r.raise_for_status()

    data = r.json()
    events = []

    for e in data.get("events", []):
        events.append({
            "title": e.get("title"),
            "description": e.get("description"),
            "start": e.get("start"),
            "end": e.get("end"),
            "location": e.get("location_name"),
            "url": e.get("url"),
            "audience": e.get("audience"),
            "source": "freelibrary-json"
        })

    return events


# def try_html(events_url):

#     HEADERS = {
#         "User-Agent": "where2play-event-agent/1.0",
#         "Accept": "application/json,text/html"
#     }

#     print("⚠️ Falling back to HTML parsing")

#     r = requests.get(events_url, headers=HEADERS, timeout=20)
#     r.raise_for_status()
#     soup = BeautifulSoup(r.text, "html.parser")

#     events = []
#     visited_urls = set()

#     # -----------------------------------------
#     # 1) Detect LibraryCalendar daily feed links
#     # -----------------------------------------
#     feed_links = set()

#     for a in soup.find_all("a", href=True):
#         href = a["href"]
#         if "/events/feed/html" in href:
#             feed_links.add(urljoin(events_url, href))

#     # -----------------------------------------
#     # 2) Parse each daily feed page
#     # -----------------------------------------
#     for feed_url in sorted(feed_links):
#         if feed_url in visited_urls:
#             continue
#         visited_urls.add(feed_url)

#         try:
#             fr = requests.get(feed_url, headers=HEADERS, timeout=20)
#             fr.raise_for_status()
#             fsoup = BeautifulSoup(fr.text, "html.parser")

#             for item in fsoup.select("li, div.event, article"):
#                 link = item.find("a", href=True)
#                 if not link:
#                     continue

#                 title = link.get_text(strip=True)
#                 if len(title) < 6:
#                     continue

#                 event_url = urljoin(feed_url, link["href"])

#                 date_el = item.find("time") or item.find(class_=lambda x: x and "date" in x.lower())
#                 location_el = item.find(class_=lambda x: x and "location" in x.lower())

#                 events.append({
#                     "title": title,
#                     "url": event_url,
#                     "date": date_el.get_text(strip=True) if date_el else None,
#                     "location": location_el.get_text(strip=True) if location_el else None,
#                     "source": "librarycalendar-html"
#                 })

#         except Exception:
#             continue

#     if events:
#         return events

#     # -----------------------------------------
#     # 3) Generic HTML fallback (non-calendar)
#     # -----------------------------------------
#     KEYWORDS = ["event", "events", "program", "story", "workshop"]

#     for a in soup.find_all("a", href=True):
#         text = a.get_text(strip=True)
#         if len(text) < 6:
#             continue

#         url = urljoin(events_url, a["href"])

#         if any(x in url.lower() for x in ["feed", "rss", "ical", "export"]):
#             continue

#         if any(k in text.lower() for k in KEYWORDS):
#             events.append({
#                 "title": text,
#                 "url": url,
#                 "source": "html-link"
#             })

#     return events if events else None


def try_html(events_url):
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

    print("⚠️ Falling back to HTML parsing")

    HEADERS = {
        "User-Agent": "where2play-event-agent/1.0",
        "Accept": "application/json,text/html"
    }
    
    # r = requests.get(events_url, headers=HEADERS, timeout=20)
    r = session.get(events_url, headers=HEADERS, timeout=20)
    
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    events = []
    visited_urls = set()

    # -----------------------------------------
    # 1) Detect LibraryCalendar daily feed links
    # -----------------------------------------
    feed_links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/events/feed/html" in href:
            feed_links.add(urljoin(events_url, href))

    # -----------------------------------------
    # 2) Parse each daily feed page
    # -----------------------------------------
    for feed_url in sorted(feed_links):
        if feed_url in visited_urls:
            continue
        visited_urls.add(feed_url)

        try:
            fr = requests.get(feed_url, headers=HEADERS, timeout=20)
            fr.raise_for_status()
            fsoup = BeautifulSoup(fr.text, "html.parser")

            for item in fsoup.select("li, div.event, article"):
                link = item.find("a", href=True)
                if not link:
                    continue

                title = link.get_text(strip=True)
                if len(title) < 6:
                    continue

                event_url = urljoin(feed_url, link["href"])

                date_el = item.find("time") or item.find(class_=lambda x: x and "date" in x.lower())
                location_el = item.find(class_=lambda x: x and "location" in x.lower())

                events.append({
                    "title": title,
                    "url": event_url,
                    "date": date_el.get_text(strip=True) if date_el else None,
                    "location": location_el.get_text(strip=True) if location_el else None,
                    "source": "librarycalendar-html"
                })

        except Exception:
            continue

    if events:
        return events

    # -----------------------------------------
    # 3) Generic HTML fallback (non-calendar)
    # -----------------------------------------
    KEYWORDS = ["event", "events", "program", "story", "workshop"]

    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        if len(text) < 6:
            continue

        url = urljoin(events_url, a["href"])

        if any(x in url.lower() for x in ["feed", "rss", "ical", "export"]):
            continue

        if any(k in text.lower() for k in KEYWORDS):
            events.append({
                "title": text,
                "url": url,
                "source": "html-link"
            })

    return events if events else None



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

def safe_get(url: str, timeout: int = 20) -> requests.Response:
    r = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout, allow_redirects=True)
    return 

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

    feed_urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/events/feed/html" in href:
            feed_urls.add(urljoin(calendar_root, href))

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
        fr = safe_get(fu)
        if fr.status_code >= 400:
            continue
        fsoup = BeautifulSoup(fr.text, "html.parser")
        # find event links
        for a in fsoup.find_all("a", href=True):
            href = a["href"]
            if "/event/" in href:
                event_urls.add(urljoin(fu, href))
        time.sleep(0.2)

    # detail pages
    events = []
    for eu in list(event_urls):
        dr = safe_get(eu)
        if dr.status_code >= 400:
            continue
        events.append(_parse_jsonld_event_detail(dr.text, eu))
        time.sleep(0.15)

    return events


def is_url_reachable(url, timeout=15):
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html"
    }

    # 1️⃣ Try HEAD first (fast, but unreliable)
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout)
        if r.status_code < 400:
            return True
        # ⚠️ Reachable but HEAD is blocked
        if r.status_code in (401, 403, 405, 429):
            pass  # fall back to GET

        # ❌ True negative (e.g. 404, 410)
        if r.status_code in (404, 410):
            return False
    except requests.RequestException:
        pass

    # 2️⃣ Fallback to GET (authoritative)
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            allow_redirects=True,
            timeout=timeout
        )
        # return r.status_code < 400
        # Treat anything except 404 as reachable
        if r.status_code == 404:
            return False
        return True
    except requests.RequestException:
        return False


def looks_like_real_html(html: str) -> bool:
    if not html:
        return False

    if len(html) < 800:
        return False

    lower = html.lower()

    # Common bot / challenge indicators
    blocked_signals = [
        "cf-browser-verification",
        "cloudflare",
        "checking your browser",
        "enable javascript",
        "please wait",
        "bot detection",
        "__cf_chl"
    ]

    if any(sig in lower for sig in blocked_signals):
        return False

    return True


def fetch_with_browser(url, timeout=30000):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(url, timeout=timeout, wait_until="networkidle")
        html = page.content()

        browser.close()
        return html


def find_upcoming_events_link(homepage_url):
    '''
    This function will find the link to the upcoming events, like a libray url address 
    "https://ccmellorlibrary.org/"

    Through this function, we are able to find the link to the upcoming events
    https://ccmellor.librarycalendar.com/

    Calling example,
        library_url = "https://ccmellorlibrary.org/"
        result = find_upcoming_events_link(library_url)
        upcoming_events = result['url']
        print(result['url'])
    '''

    # HEADERS = {
    #     "User-Agent": (
    #         "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    #         "AppleWebKit/537.36 (KHTML, like Gecko) "
    #         "Chrome/121.0.0.0 Safari/537.36"
    #     ),
    #     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    #     "Accept-Language": "en-US,en;q=0.9",
    #     "Referer": "https://www.google.com/"
    # }
    
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    KEYWORDS = [
        "event",
        "events",
        "calendar",
        "program",
        "programs",
        "upcoming",
        "youth", 
        "children",
        "kids",
        "kid"
    ]

    try:
        # r = requests.get(homepage_url, headers=HEADERS, timeout=30)
        # r.raise_for_status()
        r = requests.get(
            homepage_url,
            headers=HEADERS,
            timeout=30,
            allow_redirects=True
        )
        html = r.text
        print(f"✅ Request succeeded for {homepage_url}")
    except requests.exceptions.HTTPError as e:
        print(f"❌ Request failed for {homepage_url}: {e}")
        return None
    
    # -----------------------------
    # Step 2: Fallback to browser if blocked
    # -----------------------------
    if not looks_like_real_html(html):
        print("🧭 Falling back to browser rendering")
        try:
            print("fetching with browser")
            html = fetch_with_browser(homepage_url)
        except Exception as e:
            print(f"❌ Browser fetch failed: {e}")
            return None
    
    # print("🧭 Finished rendering", html)

    # if not is_url_reachable(homepage_url): 
    #     print(f"The website {homepage_url} is not reachable")
    #     return None

    soup = BeautifulSoup(html, "html.parser")

    candidates = []

    for a in soup.find_all("a", href=True):
        text = (a.get_text(strip=True) or "").lower()
        href = a["href"].strip()
        full_url = urljoin(homepage_url, href)

        score = 0
        reasons = []

        # 1️⃣ Text intent
        if any(k in text for k in KEYWORDS):
            score += 4
            reasons.append("keyword_in_text")

        # 2️⃣ URL intent
        if any(k in full_url.lower() for k in ["calendar", "events", "libcal"]):
            score += 3
            reasons.append("keyword_in_url")

        # 3️⃣ Button / CTA styling
        classes = " ".join(a.get("class", [])).lower()
        if any(c in classes for c in ["button", "btn", "cta"]):
            score += 2
            reasons.append("button_style")

        # # 4️⃣ External calendar platform
        # if "libcal.com" in full_url:
        #     score += 5
        #     reasons.append("libcal")

        # 4️⃣ Known calendar platforms
        if any(p in full_url for p in [
            "libcal.com",
            "librarycalendar.com",
            "calendar."
        ]):
            score += 5
            reasons.append("calendar_platform")

        if score > 0:
            candidates.append({
                "text": a.get_text(strip=True),
                "url": full_url,
                "score": score,
                "reasons": reasons
            })

    if not candidates:
        return None

    # highest score wins
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[0]['url']


if __name__ == '__main__':
    # liburl = 'https://libwww.freelibrary.org/locations/joseph-e-coleman-northwest-regional-library'
    liburl = 'https://calendar.lancasterlibraries.org/events/month?branches%5B108%5D=108'
    liburl = 'https://libwww.freelibrary.org/calendar/?location_code=QMB'
    upcoming_events_url = try_html(liburl)
    print(upcoming_events_url)


    # url = 'https://calendar.lancasterlibraries.org/events'

    # events = scrape_librarycalendar(url)


    # url = 'https://libwww.freelibrary.org/locations/joseph-e-coleman-northwest-regional-library'
    # reacheable = is_url_reachable(url)
    # print(reacheable)


    # library_url = "https://www.upperdublinlibrary.org/"
    # # library_url = 'https://www.ghal.org/'
    # result = find_upcoming_events_link(library_url)
    # # upcoming_events = result['url']
    # # print(result['url'])
    # print(result)



