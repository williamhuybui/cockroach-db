"""
Load the mock calls.csv / transcript.csv into the running API.

Run this AFTER:
1. The CockroachDB tables exist (customers, transcripts, calls, call_id_sequence).
2. The FastAPI app is running locally (python src/main.py).

Usage (from the project root, venv activated, server running in another tab):
    python src/mock_data/load_mock_data.py
"""

import csv
import os

import requests

API_BASE_URL = "http://localhost:5050"
MOCK_DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def blank_to_none(value):
    """CSV empty strings should become None for optional fields."""
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def load_transcripts():
    path = os.path.join(MOCK_DATA_DIR, "transcripts.csv")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Loading {len(rows)} transcript turns...")

    for row in rows:
        payload = {
            "call_id": blank_to_none(row["call_id"]),
            "timestamp": row["timestamp"],
            "caller_number": row["caller_number"],
            "speaker": row["speaker"],
            "text": row["text"],
        }

        response = requests.post(f"{API_BASE_URL}/transcripts", json=payload)

        if response.status_code == 201:
            continue
        elif response.status_code == 409:
            print(f"  skip (already exists): {payload['call_id']} {payload['speaker']}")
        else:
            print(f"  FAILED [{response.status_code}]: {payload['call_id']} {payload['speaker']}")
            print(f"    {response.text}")


def load_calls():
    path = os.path.join(MOCK_DATA_DIR, "calls.csv")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Loading {len(rows)} completed calls...")

    for row in rows:
        payload = {
            "call_id": row["call_id"],
            "caller_number": row["caller_number"],
            "timestamp": row["timestamp"],
            "name": blank_to_none(row["name"]),
            "email": blank_to_none(row["email"]),
            "address": blank_to_none(row["address"]),
            "problem": blank_to_none(row["problem"]),
            "problem_detail": blank_to_none(row["problem_detail"]),
            "availability": blank_to_none(row["availability"]),
            "urgency": blank_to_none(row["urgency"]),
            "previous_call_id": blank_to_none(row["previous_call_id"]),
            "calling_on_behalf_of": blank_to_none(row["calling_on_behalf_of"]),
        }

        response = requests.post(f"{API_BASE_URL}/calls", json=payload)

        if response.status_code == 201:
            continue
        elif response.status_code == 409:
            print(f"  skip (already exists): {payload['call_id']}")
        else:
            print(f"  FAILED [{response.status_code}]: {payload['call_id']}")
            print(f"    {response.text}")


if __name__ == "__main__":
    load_transcripts()
    load_calls()
    print("Done.")