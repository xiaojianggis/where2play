## This script is used to get the URL for the Google Place API
## By Xiaojiang Li, Biometeors, UPenn, Feb 23, 2026

import requests
import json

## you need to enable the place API
#https://console.cloud.google.com/google/maps-apis/api-list?project=where2play-484417
API_KEY = "AIzaSyDX5IKdkxVwPo4pXxKitRcJNTOVtZhqQKI"


# def search_place_new(query):
def search_place_new(query, lat=None, lon=None, radius_m=5000):
    url = "https://places.googleapis.com/v1/places:searchText"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
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
        "X-Goog-Api-Key": API_KEY,
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

    return r.json()


if __name__ == "__main__":
    # Step A: Search → get place_id
    data = search_place_new("Milton Public Library", 
                            lat= 41.0211393,
                            lon= -76.8440572)
    
    place_id = data["places"][0]["id"]

    # Step B: Place Details request
    details = get_place_details_new(place_id)
    
    print("Official website:", details.get("websiteUri"))
    print("Google Maps URL:", details.get("googleMapsUri"))
    print(details)

