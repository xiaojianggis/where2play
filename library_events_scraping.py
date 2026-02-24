## This script is used to parse the URL address and find the upcoming event
## this current script is only able to detect those libraries have websites
## By Xiaojiang Li, Biometeors, UPenn, Jan 15, 2025

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import json
import time
import re
import shutil
from urllib.parse import urlparse


## The events calendar maybe in four different 
# -------------------------------------------------
# 1. LIBCAL AUTO-DETECTION
# -------------------------------------------------
HEADERS = {
    "User-Agent": "where2play-event-agent/1.0",
    "Accept": "application/json,text/html"
}

def try_libcal(events_url):
    parsed = urlparse(events_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    try:
        r = requests.get(events_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        scripts = soup.find_all("script")
        calendar_id = None
        pattern1 = re.compile(r"baseCalendarId\s*:\s*(\d+)")
        pattern2 = re.compile(r"calendarId\s*=\s*(\d+)")
        for script in scripts:
            if script.string:
                match1 = pattern1.search(script.string)
                if match1:
                    calendar_id = match1.group(1)
                    break
                match2 = pattern2.search(script.string)
                if match2:
                    calendar_id = match2.group(1)
                    break
        if not calendar_id:
            return None

        print(f"Detected LibCal calendar_id={calendar_id}")

        test_url = f"{base}/ajax/calendar/list"
        events = []
        page = 1
        while True:
            params = {
                "c": calendar_id,
                "date": "0000-00-00",
                "perpage": 50,
                "page": page
            }
            data = requests.get(test_url, headers=HEADERS, params=params, timeout=15).json()
            results = data.get("results", [])
            if not results:
                break

            for e in results:
                events.append({
                    "title": e.get("title"),
                    "url": e.get("url"),
                    "date": e.get("date"),
                    "start": e.get("start"),
                    "end": e.get("end"),
                    "location": e.get("location"),
                    "description": e.get("shortdesc"),
                    "categories": [c["name"] for c in e.get("categories_arr", [])],
                    "audiences": [a["name"] for a in e.get("audiences", [])],
                    "source": "libcal"
                })

            page += 1
            time.sleep(0.3)

        return events
    except Exception:
        return None


# -------------------------------------------------
# 2. WORDPRESS (The Events Calendar) AUTO-DETECTION
# -------------------------------------------------
def try_wordpress(events_url):
    parsed = urlparse(events_url)
    api = f"{parsed.scheme}://{parsed.netloc}/wp-json/tribe/events/v1/events"

    try:
        r = requests.get(api, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None

        data = r.json()
        if "events" not in data:
            return None

        print("✅ Detected WordPress Events Calendar")

        events = []
        for e in data["events"]:
            events.append({
                "title": e["title"],
                "url": e["url"],
                "start": e["start_date"],
                "end": e["end_date"],
                "location": e.get("venue", {}).get("address"),
                "description": e.get("description"),
                "categories": [c["name"] for c in e.get("categories", [])],
                "source": "wordpress"
            })

        return events
    except Exception:
        return None


# -------------------------------------------------
# 3. ICAL AUTO-DETECTION
# -------------------------------------------------
def try_ical(events_url):
    try:
        r = requests.get(events_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        for link in soup.find_all("link", href=True):
            if "ical" in link["href"].lower():
                ical_url = urljoin(events_url, link["href"])
                print("✅ Detected iCal feed:", ical_url)
                return [{"source": "ical", "url": ical_url}]
        return None
    except Exception:
        return None


# -------------------------------------------------
# 4. HTML FALLBACK SCRAPER
# -------------------------------------------------
def try_html(events_url):
    print("⚠️ Falling back to HTML parsing")

    HEADERS = {
        "User-Agent": "where2play-event-agent/1.0",
        "Accept": "application/json,text/html"
    }
    
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

    r = session.get(events_url, headers=HEADERS, timeout=20)


    # r = requests.get(events_url, headers=HEADERS, timeout=20)
    # r.raise_for_status()
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


# -------------------------------------------------
# MAIN DISPATCHER
# -------------------------------------------------
def extract_events(events_url):
    for method in (try_libcal, try_wordpress, try_ical, try_html):
        result = method(events_url)
        if result:
            return result
    return []


## for the libray website, this one will find the link to the upcoming events
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
            print("library url is not valid, continue")
            return None
            # raise

    # if not is_url_reachable(homepage_url): 
    #     print(f"The website {homepage_url} is not reachable")
    #     return None

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
    return candidates[0]['url']


# some events are in the library calendar, this function will parse the event 
# page through the link, only be able to do for 1month
def parse_librarycalendar_event(event_url):
    '''
    This function is used to parse the URL address and check the html pages there
    and get all the event information there. 
    likely you may get event like this, https://ccmellor.librarycalendar.com/event/teen-dyi-pizza-workshop-4015
    Using this script you would be able to find all the information in the event link. This is based 
    on the calendar. 

    Calling example, 
        url = "https://ccmellor.librarycalendar.com/event/teen-dyi-pizza-workshop-4015"
        event_json = parse_librarycalendar_event(url)

        output_path = "data/events/librarycalendar_event.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(event_json, f, indent=2, ensure_ascii=False)

        print(f"✅ Event JSON saved to {output_path}")

    By Xiaojiang Li, Jan 16, 2026, Biometeors, UPenn
    '''

    # HEADERS = {
    #     "User-Agent": "where2play-event-agent/1.0",
    #     "Accept": "text/html"
    # }

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        # "Referer": "https://libwww.freelibrary.org/calendar/",
        "Connection": "keep-alive",
    }

    session = requests.Session()
    session.headers.update(HEADERS)

    r = session.get(event_url, headers=HEADERS, timeout=20)
    # r = requests.get(event_url, headers=HEADERS, timeout=20)
    # r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    event = {
        "source": "librarycalendar",
        "url": event_url
    }

    # -------------------------------------------------
    # 1) Schema.org JSON-LD (PRIMARY, most reliable)
    # -------------------------------------------------
    ld_json = soup.find("script", type="application/ld+json")
    if ld_json:
        try:
            data = json.loads(ld_json.string)

            event["title"] = data.get("name")
            event["description"] = BeautifulSoup(
                data.get("description", ""), "html.parser"
            ).get_text(" ", strip=True)

            event["start_datetime"] = data.get("startDate")
            event["end_datetime"] = data.get("endDate")

            location = data.get("location", {})
            address = location.get("address", {})

            event["location_name"] = location.get("name")
            event["address"] = {
                "street": address.get("streetAddress"),
                "city": address.get("addressLocality"),
                "state": address.get("addressRegion"),
                "zip": address.get("postalCode"),
                "country": address.get("addressCountry"),
            }

            organizer = data.get("organizer", {})
            event["organizer"] = organizer.get("name")
            event["organizer_url"] = organizer.get("url")

        except Exception:
            pass

    # -------------------------------------------------
    # 2) Target audience (age groups)
    # -------------------------------------------------
    audience = []
    for a in soup.select(".lc-event__age-groups a"):
        audience.append(a.get_text(strip=True))

    if audience:
        event["target_audience"] = audience

    # -------------------------------------------------
    # 3) Human-readable date & time (fallback / display)
    # -------------------------------------------------
    date_el = soup.select_one(".lc-event-info-item--date")
    time_el = soup.select_one(".lc-event-info-item--time")

    if date_el:
        event["date_display"] = date_el.get_text(strip=True)

    if time_el:
        event["time_display"] = time_el.get_text(strip=True)

    # -------------------------------------------------
    # 4) Contact info
    # -------------------------------------------------
    contact = {}

    name_el = soup.select_one(".lc-event-contact-name")
    email_el = soup.select_one(".lc-event-contact-email a")
    phone_el = soup.select_one(".lc-event-contact-phone a")

    if name_el:
        contact["name"] = name_el.get_text(strip=True).replace("Name:", "").strip()

    if email_el:
        contact["email"] = email_el.get_text(strip=True)

    if phone_el:
        contact["phone"] = phone_el.get_text(strip=True)

    if contact:
        event["contact"] = contact

    # -------------------------------------------------
    # 5) Normalize output schema (ensure consistency)
    # -------------------------------------------------
    event.setdefault("title", None)
    event.setdefault("description", None)
    event.setdefault("start_datetime", None)
    event.setdefault("end_datetime", None)
    event.setdefault("location_name", None)
    event.setdefault("address", {})
    event.setdefault("organizer", None)
    event.setdefault("organizer_url", None)
    event.setdefault("target_audience", [])
    event.setdefault("date_display", None)
    event.setdefault("time_display", None)
    event.setdefault("contact", {})

    return event


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


## loop_library_website, and find the upcoming event url
def loop_library_website_upcomingevent(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        libraries = json.load(f)

    print(f"📚 Total libraries: {len(libraries)}\n")
    events_list = []

    for i, lib in enumerate(libraries, start=1):
        library_url = lib.get('website')
        lat, lon = lib.get('lat'), lib.get('lon')

        if library_url is None: continue
        # print(lat, lon, library_url)
        print(lat, lon, library_url)

        time.sleep(5)
        
        if not is_url_reachable(library_url): 
            print(f"The website {library_url} is not reachable-------")
            continue

        upcoming_events_url = find_upcoming_events_link(library_url)
        print('upcoming_events_url__________', upcoming_events_url)

        # print(f"--- Library {i} ---")
        # print(f"Name: {lib.get('name')}")
        # print(f"OSM ID: {lib.get('osm_type')} {lib.get('osm_id')}")
        # print(f"Location: {lib.get('lat')}, {lib.get('lon')}")
        # print(f"Website: {lib.get('website')}")
        # print(f"Operator: {lib.get('operator')}")

        address_parts = [
            lib.get("addr_housenumber"),
            lib.get("addr_street"),
            lib.get("addr_city"),
            lib.get("addr_postcode"),
        ]
        # address = ", ".join([p for p in address_parts if p])
        events_list.append({
            'name': lib.get('name'),
            'lon': lib.get('lon'), 
            'lat': lib.get('lat'), 
            'url': upcoming_events_url,
            'address': address_parts
        })
        # print(f"Address: {address if address else 'N/A'}")
    return events_list


def library_website_upcomingevent_scrape(json_path, output_json_path):
    '''
    load the url of all the libraries in the json file and then find the link to the upcoming events
    The new upcoming event will be saved as a ne item in the output_json_path 
    '''

    # 1️⃣ Load input libraries
    with open(json_path, "r", encoding="utf-8") as f:
        libraries = json.load(f)

    print(f"📚 Total libraries: {len(libraries)}\n")

    updated_libraries = []

    # 2️⃣ Loop libraries
    for i, lib in enumerate(libraries, start=1):
        library_url = lib.get("website")
        name = lib.get("name")

        if not library_url:
            # lib["upcoming_url"] = None
            # updated_libraries.append(lib)
            continue

        print(f"The library of [{i}] {name} → {library_url}")
        time.sleep(0.5)

        if not is_url_reachable(library_url):
            print(f"⚠️ Not reachable: {library_url}")
            lib["upcoming_url"] = None
            updated_libraries.append(lib)
            continue

        upcoming_events_url = find_upcoming_events_link(library_url)
        print(" upcoming_events_url:", upcoming_events_url)

        # 3️⃣ Add new field (DO NOT remove anything else)
        lib["upcoming_url"] = upcoming_events_url

        updated_libraries.append(lib)

    # 4️⃣ Save to NEW json file
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(updated_libraries, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved updated libraries → {output_json_path}")

    return updated_libraries

def is_valid_http_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https")


if __name__ == "__main__":
    import os, os.path

    root = '../../data/elibrary'
    outfolder = f'../../data/events'

    library_file = f'{root}/pa_libraries_enriched.json'
    upevent_url_file = f'{root}/upcoming_events_url.json'

    # the first try of scape upcoming events, the results may be comple or neeed to further scrape
    events_json_folder = os.path.join(outfolder, 'library_events')
    if not os.path.exists(events_json_folder): os.makedirs(events_json_folder)

    # the final complete events json res
    final_event_json_folder = os.path.join(outfolder, 'event_jsons')
    if not os.path.exists(final_event_json_folder): os.makedirs(final_event_json_folder)
    
    ##-------------Step 1: get the url of upcoming events for all libraries------------
    # library_file = os.path.join('data/elibrary/pa_libraries_seed_small.json')
    # upevent_url_file = os.path.join('data/elibrary/upcoming_events_url_small.json')

    # loop all the library websites and check if they are reachable get the 
    ## library_name, lon, lat, library_url, address = loop_library_website_upcomingevent(library_file)
    # library_events_list = library_website_upcomingevent_scrape(library_file, upevent_url_file)


    ##-------------Step 2: get the events for all libraries------------
    with open(upevent_url_file, "r", encoding="utf-8") as f:
        libraries_events_urls = json.load(f)
    print(f"📚 Total libraries: {len(libraries_events_urls)}\n")

    events_list = []

    count = 0
    for i, lib in enumerate(libraries_events_urls, start=1):
        lib_name, lib_website, lat, lon, upcoming_url = lib.get('name'), lib.get('website'), lib.get('lat'), \
              lib.get('lon'), lib.get('upcoming_url')

        if upcoming_url is None: continue
        count += 1
        print(lib_name, lat, lon, lib_website, upcoming_url)
        
        # # make the name safe for file, like Blanche A. Nixon/Cobbs Creek Library is not good because of /
        lib_name = lib_name.strip().replace(" ", "_").split("/")[0]
        lib_events_urls_file = f"{events_json_folder}/{lib_name}_events_{lat}_{lon}.json"
        # events = extract_events(upcoming_url)
        # with open(lib_events_urls_file, "w", encoding="utf-8") as f:
        #     json.dump(events, f, indent=2, ensure_ascii=False)

        ##-------------Step 3: some json results only have the link, we need to scape the link further------------
        event_res_json_file = f"{final_event_json_folder}/{lib_name}_events_{lat}_{lon}.json"
        # if os.path.exists(event_res_json_file): continue

        with open(lib_events_urls_file, "r", encoding="utf-8") as f:
            events_json = json.load(f)

        # if the event json has the description, just use it
        if len(events_json) < 2: continue
        if 'description' in events_json[0]:
            print("just use this json")
            shutil.copy(lib_events_urls_file, event_res_json_file)
        else: # need further scrape the links
            events_json_list = []
            for i, event_json in enumerate(events_json, start=1):
                event_url = event_json['url']

                if not is_valid_http_url(event_url):
                    print(f"⚠️ Skipping non-http URL: {event_url}")
                    continue

                # print("The event url is:==========", event_url)
                event_json = parse_librarycalendar_event(event_url)
                # print("The event lib is:", event_json)
                if event_json['description'] is None: continue
                events_json_list.append(event_json)

            if len(events_json_list) == 0: continue
            # save the res json events
            with open(event_res_json_file, "w", encoding="utf-8") as f:
                json.dump(events_json_list, f, indent=2, ensure_ascii=False)

    print("The total number of libraries with upcoming events is:", count)
