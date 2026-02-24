# 1) Install deps
pip install requests openai python-dotenv rapidfuzz tqdm

export OPENAI_API_KEY="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"

## you need to enable the place API
#https://console.cloud.google.com/google/maps-apis/api-list?project=where2play-484417
export GOOGLE_PLACES_API_KEY="AIzaSyDX5IKdkxVwPo4pXxKitRcJNTOVtZhqQKI"   # optional but recommended
GOOGLE_KEY = "AIzaSyDX5IKdkxVwPo4pXxKitRcJNTOVtZhqQKI"


# 2) Step A — Get Pennsylvania libraries from OSM (Overpass)
python elibrary_osm_scraping.py


# 3) Step B — Google Places enrichment (best way to get official websites)
# This step resolves “some are open, some not” automatically — Places has business status and (often) official website.
python enrich_googleplace.py


# 4) Step C — LLM “agent” to pick the OFFICIAL website when you only have search results
# For the remaining libraries (no website), you use a search tool (SerpAPI/Bing) and then an LLM tool-call to select the official site.
python library_events_scraping.py

## ---------- This script will scape all the upcoming events for each library
# Event page URL
#    ↓
# Check if LibCal is present (ajax/calendar/list)
#    ↓
# Else check WordPress Events REST API
#    ↓
# Else check iCal
#    ↓
# Else parse HTML



