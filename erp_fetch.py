from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import time
import os
import json

# Current day
IST = pytz.timezone("Asia/Kolkata")
now = datetime.now(IST)

CURRENT_DAY_INDEX = now.weekday()
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
CURRENT_DAY_NAME = DAY_NAMES[CURRENT_DAY_INDEX]

print(f"Running for: {CURRENT_DAY_NAME} ({now.strftime('%d %b %Y, %I:%M %p IST')})")

options = webdriver.ChromeOptions()
options.add_argument("--headless")
# options.add_argument("--no-sandbox")
# options.add_argument("--disable-dev-shm-usage")
# options.add_argument("--disable-gpu")
# options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(
    options=options
)


def login():
    load_dotenv()
    driver.get("https://erp.psit.ac.in")
    wait = WebDriverWait(driver, 15)

    try:
        accept_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept')]")))
        driver.execute_script("arguments[0].click();", accept_btn)
    except:
        pass

    get_username = os.getenv("username")
    get_password = os.getenv("password")

    try:
        username_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        password_field = driver.find_element(By.NAME, "password")

        username_field.send_keys(get_username)
        time.sleep(2)
        password_field.send_keys(get_password)

        submit_button = driver.find_element(By.XPATH, "//input[@type='submit'] | //button[@type='submit']")
        driver.execute_script("arguments[0].click();", submit_button)

        try:
            WebDriverWait(driver, 20).until(EC.url_contains("/Student"))
            print("login successful")
            return True
        except:
            print("login failed - invalid credentials or unexpected redirect")
            return False

    except Exception as e:
        print("login error:", e)
        return False


def parse_attendance_stats(soup):
    target_labels = [
        "Total Lecture",
        "Total Absent + OAA",
        "O.A. Attendance",
        "Attendance % without PF",
        "How To Calculate Percentage",
        "Total PF",
        "Attendance % with PF",
    ]

    extracted = {}
    page_text = soup.get_text(separator="\n")
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]

    for i, line in enumerate(lines):
        for label in target_labels:
            if label.lower() in line.lower():
                if ":" in line:
                    parts = line.split(":", 1)
                    value = parts[1].strip() if len(parts) > 1 else ""
                elif "=" in line:
                    parts = line.split("=", 1)
                    value = parts[1].strip() if len(parts) > 1 else ""
                else:
                    value = lines[i + 1] if i + 1 < len(lines) else ""

                extracted[label] = value
                break

    return extracted


def get_attendance():
    driver.get("https://erp.psit.ac.in/Student/MyAttendanceDetail")
    wait = WebDriverWait(driver, 15)

    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        stats = parse_attendance_stats(soup)

        if stats:
            print("\n===== Attendance Summary =====")
            for label, value in stats.items():
                print(f"  {label} : {value}")
            print("==============================\n")
        else:
            print("could not find attendance stats")
            print(soup.get_text(separator="\n")[:3000])

        return stats

    except Exception as e:
        print("error loading attendance page:", e)
        return {}


def extract_timetable_for_day(soup, day_name):
    day_name_lower = day_name.lower()

    # Strategy 1: day is a column header
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if any(day_name_lower in h for h in headers):
            col_index = next(
                (i for i, h in enumerate(headers) if day_name_lower in h), None
            )
            if col_index is not None:
                slots = []
                for row in table.find_all("tr")[1:]:
                    cells = row.find_all(["td", "th"])
                    if col_index < len(cells):
                        cell_text = cells[col_index].get_text(strip=True)
                        if cell_text:
                            slots.append(cell_text)
                if slots:
                    return slots

    # Strategy 2: day is the first cell of a row
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if cells and day_name_lower in cells[0].get_text(strip=True).lower():
                slots = [c.get_text(strip=True) for c in cells[1:] if c.get_text(strip=True)]
                if slots:
                    return slots

    # Strategy 3: day appears as a heading, content in next sibling
    day_header = soup.find(
        lambda tag: tag.name in ("h2", "h3", "h4", "h5", "th", "td", "div", "span", "p")
        and day_name_lower in tag.get_text(strip=True).lower()
    )
    if day_header:
        sibling = day_header.find_next_sibling()
        while sibling:
            text = sibling.get_text(separator=" | ", strip=True)
            if text:
                return [text]
            sibling = sibling.find_next_sibling()

    return []


def get_timetable():
    driver.get("https://erp.psit.ac.in/Student/MyTimeTable")
    wait = WebDriverWait(driver, 15)

    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        slots = extract_timetable_for_day(soup, CURRENT_DAY_NAME)

        print(f"\n===== Timetable for {CURRENT_DAY_NAME} =====")
        if slots:
            for i, slot in enumerate(slots, 1):
                print(f"  Period {i}: {slot}")
        else:
            print("  no classes found")
            print(soup.get_text(separator="\n")[:3000])
        print("=" * (len(CURRENT_DAY_NAME) + 22) + "\n")

        return slots

    except Exception as e:
        print("error loading timetable page:", e)
        return []


def save_to_json(attendance, timetable, success=True):
    payload = {
        "success": success,
        "day": CURRENT_DAY_NAME,
        "date": now.strftime("%d %b %Y, %I:%M %p IST"),
        "attendance": attendance,
        "timetable": timetable
    }
    with open("data.json", "w") as f:
        json.dump(payload, f, indent=2)
    print("data saved to data.json")


#main flow
if login():
    time.sleep(2)
    attendance_data = get_attendance()
    time.sleep(2)
    timetable_data = get_timetable()
    save_to_json(attendance_data, timetable_data, success=True)
else:
    save_to_json({}, [], success=False)
    print("aborting - login unsuccessful")

driver.quit()