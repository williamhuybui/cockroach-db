"""CockroachDB access — kept simple, with one reused connection per thread.
Timings against CockroachDB Cloud that shaped this file:
    opening a connection ~485 ms   (TLS handshake)
    running a query       ~60 ms
    an extra COMMIT      ~120 ms
So each thread opens one connection and keeps it, and autocommit avoids a
BEGIN/COMMIT round trip per statement. Opening a fresh connection per query
made a single dashboard load take ~19 seconds.
FastAPI runs sync endpoints in a bounded worker threadpool, so the number of
connections stays bounded without a pool library.
"""
import os
import threading
import asyncio
from contextlib import asynccontextmanager
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
load_dotenv()
_local = threading.local()
def _connection():
    """This thread's connection, opening or reopening it as needed."""
    conn = getattr(_local, "conn", None)
    if conn is None or conn.closed:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        conn.autocommit = True
        _local.conn = conn
    return conn
def execute_sql(sql, params=None):
    """Run one statement and return its rows as dicts (empty list for non-SELECTs).
    Pass values through `params` as %s placeholders, never f-string them in.
    """
    conn = _connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else []
    except psycopg2.Error:
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None
        raise
def generate_call_id():
    """Take the next call ID from the CockroachDB sequence, e.g. "C001"."""
    rows = execute_sql("SELECT nextval('call_id_sequence') AS n")
    return f"C{rows[0]['n']:03d}"
def save_transcript_turn(call_id, timestamp, caller_number, speaker, text):
    """Insert one transcript turn and return the saved row."""
    rows = execute_sql(
        """
        INSERT INTO transcripts (call_id, "timestamp", caller_number, speaker, text)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, call_id, speaker
        """,
        (call_id, timestamp, caller_number, speaker, text),
    )
    return rows[0]


def get_transcript_for_call(call_id):
    """Return every transcript turn for one call, oldest first — used by
    post_call_extraction.py to hand the full conversation to Groq."""
    return execute_sql(
        """
        SELECT speaker, text, "timestamp"
        FROM transcripts
        WHERE call_id = %s
        ORDER BY "timestamp" ASC
        """,
        (call_id,),
    )


# ---------------------------------------------------------------------------
# Async-compatible wrapper around the sync connection above.
#
# main.py and routers/*.py were written against an async DB-API style
# (`await connection.execute(...)`, `await cursor.fetchone()`). Rather than
# rewrite that call-side code, these adapters run the underlying sync
# psycopg2 calls in a worker thread and expose the async interface those
# callers already expect — reusing the same thread-local connection from
# _connection(), not opening a second one.
# ---------------------------------------------------------------------------

class _AsyncCursorAdapter:
    """Wraps a psycopg2 cursor so `await cur.fetchone()` / `await cur.fetchall()`
    work, by running the blocking calls in a worker thread."""

    def __init__(self, cursor):
        self._cursor = cursor

    async def fetchone(self):
        return await asyncio.to_thread(self._cursor.fetchone)

    async def fetchall(self):
        return await asyncio.to_thread(self._cursor.fetchall)


class _AsyncConnectionAdapter:
    """Wraps the thread-local psycopg2 connection so `await connection.execute(...)`
    returns a cursor-like object, matching the async DB-API style routers/*.py
    was written against."""

    def __init__(self, conn):
        self._conn = conn

    async def execute(self, sql, params=None):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        await asyncio.to_thread(cur.execute, sql, params)
        return _AsyncCursorAdapter(cur)


@asynccontextmanager
async def get_database_connection():
    """Async-compatible wrapper around the thread-local connection, for read
    queries that don't need an explicit transaction."""
    conn = await asyncio.to_thread(_connection)
    yield _AsyncConnectionAdapter(conn)


@asynccontextmanager
async def get_database_transaction():
    """Same as get_database_connection, but turns off autocommit for the
    duration so multiple statements inside the block commit atomically."""
    conn = await asyncio.to_thread(_connection)
    await asyncio.to_thread(setattr, conn, "autocommit", False)
    try:
        yield _AsyncConnectionAdapter(conn)
        await asyncio.to_thread(conn.commit)
    except Exception:
        await asyncio.to_thread(conn.rollback)
        raise
    finally:
        await asyncio.to_thread(setattr, conn, "autocommit", True)


def configure_database(database_url=None):
    """Compatibility no-op: _connection() already opens lazily per-thread,
    so there's no pool to pre-open here. Kept so main.py's startup/shutdown
    code doesn't need to change."""

    class _NoPool:
        async def open(self):
            pass

        async def close(self):
            pass

    return _NoPool()


# import pandas as pd
# print(execute_sql("SELECT * FROM customers"))