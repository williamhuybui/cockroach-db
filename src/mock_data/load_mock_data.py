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
