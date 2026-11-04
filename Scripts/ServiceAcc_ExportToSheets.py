import gspread
from google.oauth2.service_account import Credentials
import sqlite3

# Define the scope of the APIs we need to access
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Load credentials
try:
    creds = Credentials.from_service_account_file(
        "Json files/Service_account_cred.json",
        scopes=scopes
    )

    client = gspread.authorize(creds)

except FileNotFoundError:
    print("Error: Service_account_cred.json not found.")
    exit()

except Exception as e:
    print(f"An error occurred during authentication: {e}")
    exit()


# Connect to Google Sheet
try:
    spreadsheet = client.open("Fitbit tracking data")
    worksheet = spreadsheet.worksheet("Manya-New style")

    print("Successfully connected to the spreadsheet.")

except gspread.exceptions.SpreadsheetNotFound:
    print("Error: Spreadsheet not found. Check the name and sharing permissions.")
    exit()


print("Reading data from database...")

# Connect to database
conn = sqlite3.connect("Database/data_15.db")
cursor = conn.cursor()

# Get heart-rate data
cursor.execute("""
    SELECT average_beats_per_minute
    FROM heart_rate_15min
    ORDER BY timestamp
""")

records = cursor.fetchall()

conn.close()

print(f"Found {len(records)} heart-rate readings.")


# Convert records into a format Google Sheets can use
values = [[record[0]] for record in records]

# Write data starting at D8
if values:
    worksheet.update(
        range_name="G8",
        values=values
    )

print("Data successfully written to Google Sheets!")