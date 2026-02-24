## The address information on the OSM is not standard and not accurate, here
## I am going to use Google Place API to enrich the complete information
## last updated by Xiaojiang Li, Biometeors, UPenn, Feb 24, 2026

# pa_enrich_google.py
import os, json, time, requests
from tqdm import tqdm
from rapidfuzz import fuzz


GOOGLE_KEY = os.getenv("AIzaSyDX5IKdkxVwPo4pXxKitRcJNTOVtZhqQKI")

## you need to enable the place API
#https://console.cloud.google.com/google/maps-apis/api-list?project=where2play-484417
GOOGLE_KEY = "AIzaSyDX5IKdkxVwPo4pXxKitRcJNTOVtZhqQKI"

# if not GOOGLE_KEY:
#     raise RuntimeError("Set GOOGLE_PLACES_API_KEY env var")

HEADERS = {"User-Agent": "pa-library-agent/1.0"}

NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


# def search_place_new(query):
def search_place_new(query, lat=None, lon=None, radius_m=5000):
    url = "https://places.googleapis.com/v1/places:searchText"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_KEY,
        "X-Goog-FieldMask": (
            "places.id,"
            "places.displayName,"
            "places.formattedAddress,"
            "places.googleMapsUri"
        )
    }

    # --- Attempt 1: text-only search ---
    payload = {
        "textQuery": query
    }

    r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()
    data = r.json()

    # If we got results, return immediately
    if data.get("places"):
        print("First attemp succeeded")
        return data
    
    # --- Attempt 2: retry with location bias ---
    if lat is not None and lon is not None:
        payload["locationBias"] = {
            "circle": {
                "center": {
                    "latitude": lat,
                    "longitude": lon
                },
                "radius": radius_m
            }
        }
        print("Second attemp succeeded")
        r = requests.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    return data


def get_place_details_new(place_id):
    url = f"https://places.googleapis.com/v1/places/{place_id}"

    headers = {
        "X-Goog-Api-Key": GOOGLE_KEY,
        "X-Goog-FieldMask": (
            "id,"
            "displayName,"
            "websiteUri,"
            "googleMapsUri,"
            "formattedAddress,"
            "types,"
            "internationalPhoneNumber,"
            "regularOpeningHours"
        )
    }

    r = requests.get(url, headers=headers)
    r.raise_for_status()

    time.sleep(1)

    return r.json()


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
    libname = lib["name"]
    print("enriching", libname, lib)
    # if lib.get("website"):
    #     return lib, "kept_osm_website"

    lat, lon = lib.get("lat"), lib.get("lon")
    # if lat is None or lon is None:
    #     return lib, "missing_coords"
    # else:

    data = search_place_new(libname, 
                            lat = lat,
                            lon = lon)
    place_id = data["places"][0]["id"]

    # Step B: Place Details request
    details = get_place_details_new(place_id)
    # website = details.get("websiteUri")

    # print("Official website:", details.get("websiteUri"))
    # print("Google Maps URL:", details.get("googleMapsUri"))

    details['name'] = libname

    return details
    

        # if website:
        #     lib["website"] = website
        #     return lib, "filled_from_google"
        # return lib, "google_no_website"


    # candidates = nearby_libraries(lat, lon)
    # if not candidates:
    #     return lib, "no_google_candidates"

    # best, score = best_match(lib["name"], candidates)
    # if not best or score < 70:
    #     return lib, f"low_name_match_{score}"

    # details = place_details(best["place_id"])
    # website = details.get("website")
    # lib["google_place_id"] = best["place_id"]
    # lib["google_match_score"] = score
    # lib["google_business_status"] = details.get("business_status")
    # lib["google_formatted_address"] = details.get("formatted_address")
    # lib["google_maps_url"] = details.get("url")

    # if website:
    #     lib["website"] = website
    #     return lib, "filled_from_google"
    # return lib, "google_no_website"


if __name__ == "__main__":
    root = '../../data/elibrary'
    library_json_file = f'{root}/pa_libraries_seed.json'
    enriched_json_file = f"{root}/pa_libraries_enriched.json"
    need_feedback_json_file = f"{root}/pa_libraries_need_fallback.json"

    libs = json.load(open(library_json_file,"r",encoding="utf-8"))
    out = []
    
    with open(enriched_json_file, "a", encoding="utf-8") as f:
        for idx, lib in enumerate(libs):
            try:
                details = enrich_one(lib)
            except Exception as e:
                print(f"Failed at {idx}: {e}")
                continue

            f.write(json.dumps(details, ensure_ascii=False) + "\n")
            f.flush()

            print(f"[{idx+1}/{len(libs)}] appended")
            time.sleep(0.05)

    # {} {} {} (and not [{}, {}]), make it valid JSON by wrapping in a list and separating with commas
    with open(enriched_json_file, encoding="utf-8") as f:
        data = [json.loads(line) for line in f if line.strip()]

    with open(f"{root}/pa_libraries_enriched_final.json", "w", encoding="utf-8") as out:
        json.dump(data, out, indent=2, ensure_ascii=False)
    