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
        # The connection may be dead (idle timeout, cluster restart). Drop it so
        # the next call reconnects instead of reusing a broken socket.
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

# import pandas as pd
# print(execute_sql("SELECT * FROM customers"))
