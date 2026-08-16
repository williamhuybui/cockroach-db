"""Backfill structured call summaries for calls that only have raw
transcripts — everything main.py already does automatically right after a
live call ends (post_call_extraction.py -> insert_call, see main.py's
post-call block), run retroactively over any call_id that never got a
`calls` row. Useful for mock/demo data loaded straight into `transcripts`,
or a live call whose post-call extraction failed at the time.

Usage:
    python scripts/backfill_call_extraction.py            # every missing call
    python scripts/backfill_call_extraction.py C001 C002  # just these
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from psycopg2.errors import ForeignKeyViolation, UniqueViolation
from pydantic import ValidationError

from api_models import CallCreate
from database import execute_sql, get_database_transaction
from post_call_extraction import extract_call_summary
from routers.calls import insert_call


def _calls_missing_a_summary(only_call_ids=None):
    """call_id/caller_number/call_started_at for every call that has
    transcript turns but no row in `calls` yet."""
    sql = """
        SELECT t.call_id,
               t.caller_number,
               min(t."timestamp") AS call_started_at
        FROM transcripts t
        LEFT JOIN calls c ON c.call_id = t.call_id
        WHERE c.call_id IS NULL
    """
    params = None
    if only_call_ids:
        sql += " AND t.call_id = ANY(%s)"
        params = (list(only_call_ids),)
    sql += ' GROUP BY t.call_id, t.caller_number ORDER BY t.call_id'
    return execute_sql(sql, params)


async def _backfill_one(call_id, caller_number, call_started_at):
    if not caller_number or caller_number == "unknown":
        print(f"{call_id}: skipped (no usable caller_number)")
        return

    # extract_call_summary re-derives the same call_started_at from the
    # transcript itself to resolve relative days ("this Friday") — passing
    # it here too just avoids re-querying the DB in insert_call's own row.
    extracted = await extract_call_summary(call_id)
    if not extracted:
        print(f"{call_id}: skipped (extraction returned nothing — see logs)")
        return

    try:
        call = CallCreate(
            call_id=call_id,
            caller_number=caller_number,
            timestamp=call_started_at,
            **extracted,
        )
    except ValidationError as error:
        print(f"{call_id}: FAILED validation — {error}")
        return

    try:
        async with get_database_transaction() as connection:
            await insert_call(connection, call)
        print(f"{call_id}: saved (urgency={call.urgency}, tags={call.tags})")
    except (UniqueViolation, ForeignKeyViolation) as error:
        print(f"{call_id}: FAILED to save — {error}")


async def main(only_call_ids):
    rows = _calls_missing_a_summary(only_call_ids)
    if not rows:
        print("Nothing to backfill — every call with transcripts already has a calls row.")
        return

    print(f"Backfilling {len(rows)} call(s)...")
    for row in rows:
        await _backfill_one(row["call_id"], row["caller_number"], row["call_started_at"])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or None))
