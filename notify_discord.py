import json
import os
import sys
import requests


def send_discord_message(data: dict):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("no DISCORD_WEBHOOK_URL found - skipping")
        return

    # Login failure 
    if not data.get("success"):
        payload = {
            "embeds": [{
                "title": "❌  ERP Login Failed",
                "description": "The scheduled fetch could not log in. Check your credentials.",
                "color": 0xED4245,
                "footer": {"text": "PSIT ERP  •  Auto-fetched via GitHub Actions"}
            }]
        }
        requests.post(webhook_url, json=payload)
        return

    day       = data.get("day", "Unknown")
    date_str  = data.get("date", "")
    attendance = data.get("attendance", {})
    timetable  = data.get("timetable", [])

    # Attendance lines 
    if attendance:
        attendance_lines = "".join(
            f"> **{label}:** {value}\n" for label, value in attendance.items()
        )
    else:
        attendance_lines = "> ⚠️ Could not fetch attendance data.\n"

    # Timetable lines 
    if timetable:
        timetable_lines = "".join(
            f"> `Period {i}` — {slot}\n" for i, slot in enumerate(timetable, 1)
        )
    else:
        timetable_lines = "> ⚠️ No classes found for today.\n"

    # ── Embed color based on attendance % 
    embed_color = 0x5865F2  # default blurple
    raw_pct = attendance.get("Attendance % without PF", "")
    try:
        pct = float("".join(c for c in raw_pct if c.isdigit() or c == "."))
        if pct >= 75:
            embed_color = 0x57F287   # green  — safe
        elif pct >= 60:
            embed_color = 0xFEE75C   # yellow — borderline
        else:
            embed_color = 0xED4245   # red    — danger
    except (ValueError, TypeError):
        pass

    payload = {
        "embeds": [{
            "title": f"  ERP Daily Report — {day}",
            "description": f"Generated on {date_str}",
            "color": embed_color,
            "fields": [
                {
                    "name": "  Attendance Summary",
                    "value": attendance_lines,
                    "inline": False
                },
                {
                    "name": f"  Today's Timetable ({day})",
                    "value": timetable_lines,
                    "inline": False
                }
            ],
            "footer": {"text": "PSIT ERP  •  Auto-fetched via GitHub Actions"}
        }]
    }

    response = requests.post(webhook_url, json=payload)
    if response.status_code == 204:
        print("discord message sent successfully")
    else:
        print(f"discord message failed: {response.status_code} — {response.text}")
        sys.exit(1)


# main 
if not os.path.exists("data.json"):
    print("data.json not found - did erp_fetch.py run?")
    sys.exit(1)

with open("data.json", "r") as f:
    data = json.load(f)

send_discord_message(data)