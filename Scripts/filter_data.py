import sqlite3
from datetime import datetime, timezone, timedelta

SOURCE_DB = "Database/rhythm.db"
OUTPUT_DB = "Database/data_15.db"


# Connect to the original database
source_conn = sqlite3.connect(SOURCE_DB)
source_cursor = source_conn.cursor()

# Get all heart-rate data
source_cursor.execute("""
    SELECT timestamp, beats_per_minute
    FROM heart_rate
    WHERE beats_per_minute IS NOT NULL
    ORDER BY timestamp
""")

records = source_cursor.fetchall()

source_conn.close()

if not records:
    print("No heart-rate data found.")
    exit()

print(f"Found {len(records)} heart-rate readings.")


# Connect to/create the new database
output_conn = sqlite3.connect(OUTPUT_DB)
output_cursor = output_conn.cursor()


# Create the new table
output_cursor.execute("""
    CREATE TABLE IF NOT EXISTS heart_rate_15min (
        timestamp TEXT PRIMARY KEY NOT NULL,
        average_beats_per_minute REAL NOT NULL
    )
""")


# Group readings into 15-minute intervals
intervals = {}

for timestamp, bpm in records:
    # Convert timestamp to datetime
    dt = datetime.fromisoformat(
        timestamp.replace("Z", "+00:00")
    )
    # Convert UTC timestamp to Eastern Time
    eastern = timezone(timedelta(hours=-4))
    dt = dt.astimezone(eastern)

    # Find the beginning of the 15-minute interval
    minute = (dt.minute // 15) * 15

    interval_start = dt.replace(
        minute=minute,
        second=0,
        microsecond=0
    )

    if interval_start not in intervals:
        intervals[interval_start] = []

    intervals[interval_start].append(float(bpm))


# Calculate average BPM for each 15-minute interval
for interval_start, bpm_values in sorted(intervals.items()):

    average_bpm = sum(bpm_values) / len(bpm_values)

    output_cursor.execute("""
        INSERT INTO heart_rate_15min
        (timestamp, average_beats_per_minute)
        VALUES (?, ?)
    """, (
        interval_start.isoformat(),
        average_bpm
    ))


# Save changes
output_conn.commit()

print(f"Created {OUTPUT_DB}")
print(f"Created {len(intervals)} 15-minute averages.")
print("15-MINUTE HEART RATE DATA")
print(f"{'Time':<35} {'Average BPM':>15}")

for interval_start, bpm_values in sorted(intervals.items()):

    average_bpm = sum(bpm_values) / len(bpm_values)

    print(
        f"{interval_start.strftime('%Y-%m-%d %I:%M %p'):<35}"
        f"{average_bpm:>15.1f}"
    )

output_conn.close()