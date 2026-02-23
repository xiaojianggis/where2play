# pa_enrich_google.py
import os, json, time, requests
from tqdm import tqdm
from rapidfuzz import fuzz

GOOGLE_KEY = os.getenv("AIzaSyDX5IKdkxVwPo4pXxKitRcJNTOVtZhqQKI")
# if not GOOGLE_KEY:
#     raise RuntimeError("Set GOOGLE_PLACES_API_KEY env var")

HEADERS = {"User-Agent": "pa-library-agent/1.0"}

NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def nearby_libraries(lat, lon, radius_m=1500):
    params = {"location": f"{lat},{lon}", "radius": radius_m, "type": "library", "key": GOOGLE_KEY}
    r = requests.get(NEARBY_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])

def place_details(place_id):
    params = {"place_id": place_id, "fields": "name,website,business_status,formatted_address,url", "key": GOOGLE_KEY}
    r = requests.get(DETAILS_URL, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get("result", {})

def best_match(target_name, candidates):
    best = None
    best_score = -1
    for c in candidates:
        score = fuzz.token_set_ratio(target_name, c.get("name",""))
        if score > best_score:
            best_score = score
            best = c
    return best, best_score

def enrich_one(lib):
    if lib.get("website"):
        return lib, "kept_osm_website"

    lat, lon = lib.get("lat"), lib.get("lon")
    if lat is None or lon is None:
        return lib, "missing_coords"

    candidates = nearby_libraries(lat, lon)
    if not candidates:
        return lib, "no_google_candidates"

    best, score = best_match(lib["name"], candidates)
    if not best or score < 70:
        return lib, f"low_name_match_{score}"

    details = place_details(best["place_id"])
    website = details.get("website")
    lib["google_place_id"] = best["place_id"]
    lib["google_match_score"] = score
    lib["google_business_status"] = details.get("business_status")
    lib["google_formatted_address"] = details.get("formatted_address")
    lib["google_maps_url"] = details.get("url")
    if website:
        lib["website"] = website
        return lib, "filled_from_google"
    return lib, "google_no_website"

if __name__ == "__main__":
    libs = json.load(open("pa_libraries_seed.json","r",encoding="utf-8"))
    out, failures = [], []

    for lib in tqdm(libs):
        lib2, status = enrich_one(lib)
        lib2["enrichment_status"] = status
        out.append(lib2)
        if status not in ("kept_osm_website","filled_from_google"):
            failures.append(lib2)
        time.sleep(0.05)  # be polite / avoid quota spikes

    json.dump(out, open("pa_libraries_enriched.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump(failures, open("pa_libraries_need_fallback.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)

    print(f"Saved: {len(out)} total → pa_libraries_enriched.json")
    print(f"Needs fallback: {len(failures)} → pa_libraries_need_fallback.json")


    