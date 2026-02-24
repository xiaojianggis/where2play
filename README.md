# Where2Play 🎈

Where2Play is a location-based application designed to help families discover **kid-friendly activities, play spaces, and events** in their communities. By combining mapping, curated data, and (optionally) AI-assisted analysis, the platform makes it easier for parents and caregivers to find safe, engaging, and accessible places for children to play.

---

## ✨ Features

- 🗺 Interactive map of kid-friendly locations and events  
- 📍 Location-based search and filtering  
- 🧒 Focus on playgrounds, libraries, story times, indoor play, and outdoor activities  
- 📅 Event aggregation (e.g., library story time, community programs)  
- 📱 Designed for mobile-first experiences  
- 🤖 (Optional) AI-powered recommendations and data enrichment  

---

## 🏗 Project Structure

```text
where2play/
├── frontend/          # Mobile or web front-end (React / SwiftUI / etc.)
├── backend/           # API services and data processing
├── data/              # Sample datasets, scraped event data, or static JSON
├── scripts/           # Data collection, scraping, or preprocessing scripts
├── docs/              # Documentation and design notes
└── README.md

```
#### Step 1. Web scrapping from OSM

We can get the location of all libraries from the OpenStreetMap

```python
python elibrary_osm_scraping.py
```


#### Step 2. Enrich the information using Google Maps 
The downloaded library information from OSM is not complete, therefore, we need to further enrich the information and standarize the format. Here the lon, lat and the name of the libarary will be further put into Google Maps and get more details information there. 

```python
python enrich_googleplace.py
```

#### Step 3. Scrape all the library website get the events information
It is the time to scrape all the library websites and get the information for all events there. 

><p>This is more details about how to do the scrapping on different types of systems</p>

>><p>some are </p>
> - test







