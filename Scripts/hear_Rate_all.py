import os
import sqlite3
import requests
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

TOKEN_FOLDER = "JSON_Files/Tokens"
CLIENT_FOLDER = "JSON_Files/Clients"
DATABASE_FILE = "Database/HRV_AllClients.db"

HEART_RATE_URL = "https://health.googleapis.com/v4/users/me/dataTypes/heart-rate/dataPoints"


def save_credentials(credentials, token_file):
    with open(token_file, "w") as file:
        file.write(credentials.to_json())


def load_credentials(token_file):
    if not os.path.exists(token_file):
        raise FileNotFoundError(f"Token file not found: {token_file}")

    credentials = Credentials.from_authorized_user_file(token_file)

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

        print("\nAccess token expired or invalid. Refreshing access token...")
        credentials.refresh(Request())
        save_credentials(credentials, token_file)

    if not credentials.valid:
        raise RuntimeError("Credentials are still invalid after refreshing.")

    return credentials


def create_database():
    db_dir = os.path.dirname(DATABASE_FILE)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    connection = sqlite3.connect(DATABASE_FILE)
    cursor = connection.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS heart_rate (
               user_id TEXT NOT NULL,
               timestamp TEXT NOT NULL,
               beats_per_minute INTEGER NOT NULL,
               PRIMARY KEY (user_id, timestamp)
           )"""
    )
    connection.commit()
    return connection


def get_all_data(credentials, token_file):
    """Fetch every available heart-rate data point (no time filter), following all pages."""
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Accept": "application/json",
    }

    all_data_points = []
    page_token = None
    page_number = 0

    print("\nRequesting ALL available heart-rate data")
    while True:
        params = {"pageSize": 10000}
        if page_token:
            params["pageToken"] = page_token

        response = requests.get(HEART_RATE_URL, headers=headers, params=params, timeout=60)

        # If authentication fails, attempt one refresh and retry.
        if response.status_code == 401:
            print("Authentication failed. Attempting refresh...")

            if not credentials.refresh_token:
                print("No refresh token available. Run OAuth_token.py to authorize again.")
                print(response.text)
                return all_data_points

            try:
                credentials.refresh(Request())
                save_credentials(credentials, token_file)
                headers["Authorization"] = f"Bearer {credentials.token}"
                response = requests.get(HEART_RATE_URL, headers=headers, params=params, timeout=60)
                print("HTTP Status after refresh:", response.status_code)
            except Exception as error:
                print("Token refresh failed:", error)
                return all_data_points

        if response.status_code != 200:
            print("\nAPI Error:", response.status_code)
            print(response.text)
            # Return what was collected so far instead of discarding it.
            return all_data_points

        data = response.json()
        data_points = data.get("dataPoints", [])
        all_data_points.extend(data_points)
        page_number += 1
        print(f"  Page {page_number}: {len(data_points)} points " f"(total so far: {len(all_data_points)})")
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    print("\nTotal heart-rate data points:", len(all_data_points))
    return all_data_points


def store_heart_rate(connection, data_points, user_id):
    cursor = connection.cursor()
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

        cursor.execute(
            "INSERT OR IGNORE INTO heart_rate (user_id, timestamp, beats_per_minute) "
            "VALUES (?, ?, ?)",
            (user_id, timestamp, bpm),
        )

        if cursor.rowcount == 1:
            inserted += 1
        else:
            skipped += 1

    connection.commit()

    print("DATABASE UPDATE for user", user_id)
    print("New records inserted:", inserted)
    print("Duplicate/invalid records skipped:", skipped)


if __name__ == "__main__":
    print("RHYTHM - HEART RATE COLLECTOR (ALL AVAILABLE DATA)")
    print("*" * 60)

    connection = create_database()

    try:
        token_files = sorted(
            f for f in os.listdir(TOKEN_FOLDER) if f.lower().endswith(".json")
        )

        for filename in token_files:
            token_file = os.path.join(TOKEN_FOLDER, filename)
            # Stable ID based on the token file name (e.g. "client1.json" -> "client1").
            user_id = os.path.splitext(filename)[0]

            try:
                credentials = load_credentials(token_file)
                data_points = get_all_data(credentials, token_file)
                if data_points:
                    store_heart_rate(connection, data_points, user_id)
                else:
                    print(f"No data points returned for {filename}")
            except Exception as error:
                # One bad token file shouldn't stop the others.
                print(f"Skipping {filename}: {error}")
    finally:
        connection.close()

    print("\nDatabase:", DATABASE_FILE)