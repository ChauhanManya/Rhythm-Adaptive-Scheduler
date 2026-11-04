
import os
import sqlite3
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

#currently only takes one specific token file
TOKEN_FOLDER = "JSON_Files/Tokens"
CLIENT_FOLDER = "JSON_Files/Clients"

# old databse DATABASE_FILE = "Database/Rhythm.db"
DATABASE_FILE = "Database/AllClients.db"

HEART_RATE_URL = (
    "https://health.googleapis.com/v4/users/me/dataTypes/heart-rate/dataPoints"
)

EASTERN = ZoneInfo("America/New_York")

def load_credentials(token_file):

    if not os.path.exists(token_file):
        raise FileNotFoundError( f"Token file not found: {token_file}")

    credentials = Credentials.from_authorized_user_file( token_file)

    print("\nToken file:", token_file)
    print("Token scopes:", credentials.scopes)
    print("Refresh token available:", bool(credentials.refresh_token))

    # Refresh the access token if credentials are invalid.
    if not credentials.valid:
        if not credentials.refresh_token:
            raise RuntimeError(
                "No refresh token is available. "
                "Run OAuth_token.py again to authorize "
                "and obtain a refresh token."
            )

        print("\nAccess token expired or invalid.")
        print("Refreshing access token...")

        credentials.refresh(Request())

        # Save the complete updated credentials.
        with open(token_file, "w") as file:
            file.write(credentials.to_json())

        
    print("Configured scopes:", credentials.scopes)
    print("Granted scopes:", credentials.granted_scopes)
    if not credentials.valid:
        raise RuntimeError( "Credentials are still invalid after refreshing.")

    return credentials

def create_database(user_id):
    os.makedirs(os.path.dirname(DATABASE_FILE),exist_ok=True)
    connection = sqlite3.connect(DATABASE_FILE)# make database if it doesn't exist
    cursor = connection.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS heart_rate (user_id TEXT NOT, timestamp TEXT NOT NULL, beats_per_minute INTEGER NOT NULL, PRIMARY KEY (user_id, timestamp))""")
    connection.commit()
    return connection

def get_last_24_hours(credentials):
    # Get today's midnight in Eastern Time.
    now_eastern = datetime.now(EASTERN)
    today_start = now_eastern.replace(hour=0,minute=0,second=0,microsecond=0)
    # Previous calendar day's midnight.
    yesterday_start = today_start - timedelta(days=1)
    # Convert the boundaries to UTC for the API.
    start_time = yesterday_start.astimezone(timezone.utc)
    end_time = today_start.astimezone(timezone.utc)

    start_string = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_string = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    filter_string = (
        f'heart_rate.sample_time.physical_time >= "{start_string}" '
        f'AND heart_rate.sample_time.physical_time < "{end_string}"'
    )

    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Accept": "application/json"
    }

    all_data_points = []
    page_token = None

    print("\nRequesting previous-day heart-rate data")
    print("\nPrevious day:")
    print(
        yesterday_start.strftime("%Y-%m-%d 12:00 AM")
        + " → "
        + (today_start - timedelta(seconds=1)).strftime(
            "%Y-%m-%d 11:59:59 PM"
        )
    )

    print("\nAPI Start (UTC):", start_string)
    print("API End (UTC):  ", end_string)

    while True:

        params = {
            "pageSize": 10000,
            "filter": filter_string
        }

        if page_token:
            params["pageToken"] = page_token

        response = requests.get(HEART_RATE_URL,headers=headers,params=params,timeout=60)
        print("\nHTTP Status:", response.status_code)

        # If authentication fails, attempt one refresh and retry.
        if response.status_code == 401:

            print("Authentication failed. Attempting refresh...")

            if not credentials.refresh_token:
                print(
                    "No refresh token available. "
                    "Run OAuth_token.py to authorize again."
                )
                print(response.text)
                return []

            try:
                credentials.refresh(Request())
                with open(token_file, "w") as file:
                    file.write(credentials.to_json())
                headers["Authorization"] = (f"Bearer {credentials.token}")
                response = requests.get(HEART_RATE_URL,headers=headers,params=params,timeout=60)
                print("HTTP Status after refresh:",response.status_code)

            except Exception as error:
                print("Token refresh failed:", error)
                return []

        if response.status_code != 200:
            print("\nAPI Error:")
            print(response.text)
            return []

        data = response.json()
        data_points = data.get("dataPoints", [])
        all_data_points.extend(data_points)
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    print("\nTotal heart-rate data points:", len(all_data_points))
    return all_data_points

def store_heart_rate(connection, data_points, user_id):

    cursor = connection.cursor()
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    inserted = 0
    skipped = 0

    for point in data_points:
        heart_rate = point.get("heartRate", {})
        sample_time = heart_rate.get("sampleTime", {})
        timestamp = sample_time.get("physicalTime")
        bpm = heart_rate.get("beatsPerMinute")

        if not timestamp or bpm is None:
            skipped += 1
            continue
        try:
            bpm = int(bpm)
        except (TypeError, ValueError):
            skipped += 1
            continue

        cursor.execute( """INSERT OR IGNORE INTO heart_rate (user_id, timestamp, beats_per_minute) VALUES (?, ?, ?)""", (user_id, timestamp, bpm))

        if cursor.rowcount == 1:
            inserted += 1
        else:
            skipped += 1

    connection.commit()

    print("DATABASE UPDATE")
    print("New records inserted:", inserted)
    print("Duplicate records skipped:", skipped)

if __name__ == "__main__":
    
    print("RHYTHM - HEART RATE COLLECTOR")
    user_id = 0
    connection = create_database(user_id)
    for filename in os.listdir(TOKEN_FOLDER ):
        user_id = user_id + 1
        token_file = os.path.join(TOKEN_FOLDER, filename)
        credentials = load_credentials(token_file)
        data_points = get_last_24_hours(credentials)
        if data_points:
            store_heart_rate(connection, data_points, user_id)
        connection.close()

    print("\nDatabase:", DATABASE_FILE)

