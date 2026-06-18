import sqlite3
import json
from datetime import datetime

DB_NAME = "travel_planner.db"


def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS travel_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        travel_data TEXT,
        itinerary TEXT
    )
    """)

    conn.commit()
    conn.close()


def save_trip(travel_data: dict, itinerary: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO travel_history (timestamp, travel_data, itinerary)
        VALUES (?, ?, ?)
    """, (
        datetime.now().isoformat(),
        json.dumps(travel_data),
        itinerary
    ))

    conn.commit()
    conn.close()


def load_trips(limit=20):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, timestamp, travel_data, itinerary
        FROM travel_history
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "timestamp": r[1],
            "travel_data": json.loads(r[2]),
            "itinerary": r[3]
        }
        for r in rows
    ]
