"""
Load the mock calls.csv / transcripts.csv straight into CockroachDB.

This used to POST to /transcripts and /calls, but neither route is mounted
on the running app anymore (only register_dashboard(app)'s /api/* routes
are — see src/main.py). Rather than stand up dead HTTP endpoints just for a
mock loader, this writes through the same functions the real call path
uses: database.save_transcript_turn (src/main.py's save_conversation_turn
calls the same one) and routers/calls.py's insert_call (which validates the
row, upserts the customer, and creates follow-up tasks exactly like a real
completed call would).

The mock call IDs (C051-C065) were deliberately chosen to continue after
whatever real calls already exist in your database — check before re-running
this against a database that already has calls in that range, since
insert_call has no upsert path and will fail on a duplicate call_id.

Usage (from the project root, venv activated — no server needs to be
running, this talks to the database directly):
    python src/mock_data/load_mock_data.py
"""

import asyncio
import csv
import os
import sys

MOCK_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(MOCK_DATA_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from api_models import CallCreate
from database import execute_sql, get_database_transaction, save_transcript_turn
from routers.calls import insert_call


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

    existing = {
        r["call_id"]
        for r in execute_sql(
            "SELECT DISTINCT call_id FROM transcripts WHERE call_id = ANY(%s)",
            (list({row["call_id"] for row in rows}),),
        )
    }

    skipped = 0
    for row in rows:
        if row["call_id"] in existing:
            skipped += 1
            continue
        save_transcript_turn(
            row["call_id"],
            row["timestamp"],
            row["caller_number"],
            row["speaker"],
            row["text"],
        )

    if skipped:
        print(f"  skipped {skipped} turns for call_ids that already have transcripts")


async def load_calls():
    path = os.path.join(MOCK_DATA_DIR, "calls.csv")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Loading {len(rows)} completed calls...")

    for row in rows:
        call_id = row["call_id"]
        already_exists = execute_sql("SELECT 1 FROM calls WHERE call_id = %s", (call_id,))
        if already_exists:
            print(f"  skip (already exists): {call_id}")
            continue

        call = CallCreate(
            call_id=call_id,
            caller_number=row["caller_number"],
            timestamp=row["timestamp"],
            name=blank_to_none(row["name"]),
            email=blank_to_none(row["email"]),
            address=blank_to_none(row["address"]),
            problem=blank_to_none(row["problem"]),
            problem_detail=blank_to_none(row["problem_detail"]),
            availability=blank_to_none(row["availability"]),
            urgency=blank_to_none(row["urgency"]),
            previous_call_id=blank_to_none(row["previous_call_id"]),
            calling_on_behalf_of=blank_to_none(row["calling_on_behalf_of"]),
        )

        try:
            async with get_database_transaction() as connection:
                await insert_call(connection, call)
        except Exception as error:
            print(f"  FAILED: {call_id}")
            print(f"    {error}")


def bump_call_id_sequence():
    """
    Advance call_id_sequence past the highest call_id just loaded, so the
    next real call (generate_call_id in database.py) can't collide with
    these mock rows.
    """
    highest = execute_sql("SELECT max(call_id) AS m FROM calls")[0]["m"]
    if not highest:
        return
    n = int(highest[1:])
    current = execute_sql("SELECT last_value FROM call_id_sequence")[0]["last_value"]
    if n > current:
        execute_sql("SELECT setval('call_id_sequence', %s)", (n,))
        print(f"Advanced call_id_sequence to {n} so future real calls start at C{n + 1:03d}.")


if __name__ == "__main__":
    load_transcripts()
    asyncio.run(load_calls())
    bump_call_id_sequence()
    print("Done.")
