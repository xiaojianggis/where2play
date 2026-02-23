import json
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
client = OpenAI()


TOOL = [{
  "type": "function",
  "name": "choose_calendar_root",
  "description": "Choose the best calendar root URL for a library and identify the platform type.",
  "parameters": {
    "type": "object",
    "properties": {
      "calendar_root": {"type": ["string","null"]},
      "platform": {
        "type": "string",
        "enum": ["libcal", "librarycalendar", "wordpress_tec", "wordpress_other", "other", "unknown"]
      },
      "confidence": {"type": "number"},
      "notes": {"type": "string"}
    },
    "required": ["calendar_root","platform","confidence","notes"]
  }
}]

def judge_calendar_link(library_name: str, homepage_url: str, links: list[dict]) -> dict:
    # Keep prompt compact but grounded.
    prompt = f"""
You are an agent that finds a library's EVENTS calendar page.

Library: {library_name}
Homepage: {homepage_url}

Candidate links (JSON):
{json.dumps(links[:120], ensure_ascii=False)}

Rules:
- Prefer the calendar ROOT, not a specific month/day view.
- Prefer official event platforms:
  * LibCal: domain contains 'libcal.com' or pages that look like LibCal.
  * LibraryCalendar: domain contains 'librarycalendar.com' OR /events routes with Drupal event pages.
  * WordPress TEC: /wp-json/tribe/events/v1 exists.
- Avoid social media, RSS-only, iCal-only, PDFs unless no better option.
Return a tool call.
"""
    resp = client.responses.create(
        model="gpt-5",
        tools=TOOL,
        input=[{"role":"user","content":prompt}],
    )

    for item in resp.output:
        if item.type == "function_call" and item.name == "choose_calendar_root":
            return item.arguments

    # Fallback if model returns plain text (rare)
    return {"calendar_root": None, "platform": "unknown", "confidence": 0.0, "notes": "no_tool_call"}

