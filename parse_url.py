
import requests
import time
import json


BASE_URL = "https://ccls.libcal.com"
CALENDAR_ID = 13410


def fetch_libcal_events():
    events = []
    page = 1
    while True:
        params = {
            "c": CALENDAR_ID,
            "date": "0000-00-00",
            "perpage": 50,
            "page": page
        }
        response = requests.get(f"{BASE_URL}/ajax/calendar/list", params=params)
        response.raise_for_status()
        data = response.json()
        page_events = data.get("results", [])
        if not page_events:
            break

        for e in page_events:
            event = {
                "id": e.get("id"),
                "title": e.get("title"),
                "url": e.get("url"),
                "date": e.get("date"),
                "start": e.get("start"),
                "end": e.get("end"),
                "campus": e.get("campus"),
                "location": e.get("location"),
                "shortdesc": e.get("shortdesc"),
                "categories_arr": [cat.get("name") for cat in e.get("categories_arr", []) if cat.get("name")],
                "audiences": [aud.get("name") for aud in e.get("audiences", []) if aud.get("name")]
            }
            events.append(event)

        print(f"Page {page}: Collected {len(page_events)} events, total so far: {len(events)}")
        page += 1
        time.sleep(0.3)

    return events


if __name__ == "__main__":
    events = fetch_libcal_events()
    with open("honeybrook_libcal_events.json", "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(events)} events to honeybrook_libcal_events.json")

