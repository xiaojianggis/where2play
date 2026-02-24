## This script is used to scrape the list of all libraries in Pennsylvania
## by Xiaojiang Li, Biometeors, UPenn, Jan 15, 2026

# pa_discover_osm.py
import json, requests
import os, os.path

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter"
]

QUERY = """
[out:json][timeout:120];
area["name"="Pennsylvania"]["admin_level"="4"]->.pa;
(
  node["amenity"="library"](area.pa);
  way["amenity"="library"](area.pa);
  relation["amenity"="library"](area.pa);
);
out tags center;
"""

HEADERS = {"User-Agent": "pa-library-agent/1.0 (contact: you@example.com)"}

def get_pa_libraries():
    for url in OVERPASS_URLS:
        try:
            r = requests.post(url, data=QUERY, headers=HEADERS, timeout=180)
            if r.status_code != 200 or not r.text.strip():
                continue
            return r.json()
        except Exception:
            continue
    raise RuntimeError("All Overpass endpoints failed")

def normalize(overpass_json):
    libs = []
    for el in overpass_json.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        libs.append({
            "osm_type": el.get("type"),
            "osm_id": el.get("id"),
            "name": name,
            "lat": lat,
            "lon": lon,
            "website": tags.get("website") or tags.get("contact:website"),
            "operator": tags.get("operator"),
            "addr_city": tags.get("addr:city"),
            "addr_postcode": tags.get("addr:postcode"),
            "addr_street": tags.get("addr:street"),
            "addr_housenumber": tags.get("addr:housenumber"),
        })
    return libs


if __name__ == "__main__":
    raw = get_pa_libraries()
    seed = normalize(raw)
    
    outfolder = "../../data/elibrary"
    if not os.path.exists(outfolder):
        os.makedirs(outfolder)
    with open(f"{outfolder}/pa_libraries_seed.json", "w", encoding="utf-8") as f:
        json.dump(seed, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(seed)} libraries to pa_libraries_seed.json")
