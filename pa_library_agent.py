import json
import os
from utils import is_url_reachable, safe_get, extract_links, normalize_event, ensure_dir, sha1, sleep_polite
from agent import judge_calendar_link
from scrapers import scrape_libcal, scrape_librarycalendar, scrape_wordpress_tec, scrape_generic_html

INPUT_LIBS = "data/elibrary/pa_libraries_seed.json"
OUT_DIR = "output/events_by_library"
OUT_ALL = "output/pa_events_all.json"
OUT_FAIL = "output/pa_events_failed.json"


if not os.path.exists(OUT_DIR):
    os.makedirs(OUT_DIR)


def ensure_dict(decision):
    if isinstance(decision, dict):
        return decision

    if isinstance(decision, str):
        try:
            parsed = json.loads(decision)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Safe fallback
    return {
        "calendar_root": None,
        "platform": "unknown",
        "confidence": 0.0,
        "notes": "failed_to_parse_agent_output"
    }


def scrape_one_library(lib: dict):
    name = lib.get("name")
    website = lib.get("website")
    if not website:
        return [], {"library": name, "reason": "missing_website"}

    if not is_url_reachable(website):
        return [], {"library": name, "website": website, "reason": "unreachable"}

    # fetch homepage
    r = safe_get(website)
    if r.status_code >= 400:
        return [], {"library": name, "website": website, "reason": f"http_{r.status_code}"}

    links = extract_links(r.text, website)

    # LLM agent chooses calendar root and platform
    decision_raw = judge_calendar_link(name, website, links)

    decision = ensure_dict(decision_raw)
    print("The decision is------------:",type(decision), decision, name, website)


    cal_root = decision.get("calendar_root")
    platform = decision.get("platform")

    if not cal_root:
        # fallback to "website/events"
        cal_root = website.rstrip("/") + "/events"
        platform = "unknown"

    # route
    norm = []
    if platform == "libcal":
        print("libcal")
        try:
            events = scrape_libcal(cal_root)
        except Exception as e:
            print(e)
            return norm, None
    elif platform == "librarycalendar":
        print("librarycalendar")
        try:
            events = scrape_librarycalendar(cal_root)
        except Exception as e:
            print(e)
            return norm, None
    elif platform == "wordpress_tec":
        print("wordpress_tec")
        try:
            events = scrape_wordpress_tec(cal_root)
        except Exception as e:
            print(e)
            return norm, None
    else:
        # try generic HTML
        print("generic_html")
        try:
            events = scrape_generic_html(cal_root)
        except Exception as e:
            print(e)
            return norm, None
    
    # attach library metadata + normalize
    for e in events:
        e["library_name"] = name
        e["library_website"] = website
        norm.append(normalize_event(e))

    return norm, None


def main():
    ensure_dir("output")
    ensure_dir(OUT_DIR)

    libs = json.load(open(INPUT_LIBS, "r", encoding="utf-8"))
    all_events = []
    failures = []

    for i, lib in enumerate(libs, start=1):
        name = lib.get("name")
        print(f"[{i}/{len(libs)}] {name}")

        safe_name = name.strip().replace(" ", "_")
        out_path = os.path.join(OUT_DIR, f"{safe_name}.json")
        print("out_path name is---------", out_path)
        if os.path.exists(out_path):
            print(f"{out_path} is already done")
            continue
        
        events, err = scrape_one_library(lib)

        if err:
            failures.append(err)
            continue

        # save per library
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)

        all_events.extend(events)
        sleep_polite(3)

    with open(OUT_ALL, "w", encoding="utf-8") as f:
        json.dump(all_events, f, indent=2, ensure_ascii=False)

    with open(OUT_FAIL, "w", encoding="utf-8") as f:
        json.dump(failures, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Total events: {len(all_events)} → {OUT_ALL}")
    print(f"⚠️ Failures: {len(failures)} → {OUT_FAIL}")


if __name__ == "__main__":
    main()
    
