import gspread
from google.oauth2.service_account import Credentials
import sqlite3

from datetime import datetime
from zoneinfo import ZoneInfo


SERVICE_ACCOUNT_FILE = "Json files/Service_account_cred.json"
DATABASE_FILE = "Database/data_15.db"
SPREADSHEET_NAME = "Fitbit tracking data"
WORKSHEET_NAME = "Manya-New style"

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=scopes
)

client = gspread.authorize(creds)
spreadsheet = client.open(SPREADSHEET_NAME)
worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

print("Successfully connected to the spreadsheet.")


sheet_date = worksheet.acell("C5").value.strip()
print("\nDate in Google Sheet:", sheet_date)

# Convert 10/07 → 2026-10-07
current_year = datetime.now().year

sheet_date_obj = datetime.strptime(
    f"{sheet_date}/{current_year}",
    "%m/%d/%Y"
)

sheet_date_formatted = sheet_date_obj.strftime("%Y-%m-%d")

print("Sheet date:", sheet_date_formatted)
print("\nReading data from database...")

conn = sqlite3.connect(DATABASE_FILE)
cursor = conn.cursor()

cursor.execute("""
    SELECT timestamp, average_beats_per_minute
    FROM heart_rate_15min
    ORDER BY timestamp
""")
records = cursor.fetchall()
conn.close()
print(f"Found {len(records)} records in database.")

eastern = ZoneInfo("America/New_York")
database_records = {}
for timestamp, average_bpm in records:

    dt = datetime.fromisoformat(
        timestamp.replace("Z", "+00:00")
    )

    dt_eastern = dt.astimezone(eastern)

    date = dt_eastern.strftime("%Y-%m-%d")
    time = dt_eastern.strftime("%H:%M")

    database_records[(date, time)] = average_bpm

database_dates = set()

for date, time in database_records.keys():
    database_dates.add(date)

print("\nDates found in database:")

for date in sorted(database_dates):
    print("-", date)


if sheet_date_formatted not in database_dates:

    print("\nWARNING:")
    print("The date in the Google Sheet does not match")
    exit()

# --------------------------------------------------
# READ TIMES FROM GOOGLE SHEET
# --------------------------------------------------

# Row 8 onward
sheet_rows = worksheet.get_all_values()[8:]
time_to_row = {}

for row_number, row in enumerate(sheet_rows, start=8):

    time_value = row[0].strip()

    try:
        time_obj = datetime.strptime(
            time_value,
            "%H:%M"
        )

        formatted_time = time_obj.strftime("%H:%M")

    except ValueError:

        try:
            time_obj = datetime.strptime(
                time_value,
                "%I:%M"
            )

            formatted_time = time_obj.strftime("%H:%M")

        except ValueError:
            print(
                f"Could not understand time '{time_value}' "
                f"in row {row_number}"
            )
            continue

    time_to_row[formatted_time] = row_number

updates = []
matched = 0
not_found = 0

for (date, time), average_bpm in database_records.items():

    # Only use data from the date in B5
    if date != sheet_date_formatted:
        continue

    if time in time_to_row:

        row_number = time_to_row[time]

        # Column C = Average heart rate
        updates.append({
            "range": f"C{row_number}",
            "values": [[average_bpm]]
        })

        matched += 1

    else:

        print(
            f"Time {time} from database "
            f"was not found in Google Sheet."
        )

        not_found += 1


# --------------------------------------------------
# WRITE DATA TO GOOGLE SHEET
# --------------------------------------------------

if updates:

    worksheet.batch_update(
        updates,
        value_input_option="USER_ENTERED"
    )

    print("\nHeart-rate data successfully updated.")

else:

    print("\nNo matching data found.")


# --------------------------------------------------
# SUMMARY
# --------------------------------------------------


print("UPDATE SUMMARY")
print("Sheet date:", sheet_date_formatted)
print("Database records:", len(records))
print("Matched records:", matched)
print("Times not found:", not_found)