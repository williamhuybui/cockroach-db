"""
Create the CockroachDB objects required by the application.

This script applies the application schema.

The schema creates:

- call_id_sequence
- customers
- calls
- transcripts
- regular indexes

The script reads DATABASE_URL from the repository-level .env file.
It can be rerun safely because the SQL file uses IF NOT EXISTS.
"""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Create the application sequence, tables, constraints, and indexes.
INITIAL_SCHEMA_FILE = (
    PROJECT_ROOT
    / "migrations"
    / "001_initial_schema.sql"
)


def get_database_url() -> str:
    """
    Load and return DATABASE_URL from the repository .env file.

    This script runs separately from FastAPI, so it must load the
    environment variables itself.
    """

    load_dotenv(
        PROJECT_ROOT / ".env"
    )

    database_url = os.getenv(
        "DATABASE_URL"
    )

    if (
        database_url is None
        or not database_url.strip()
    ):
        raise RuntimeError(
            "Missing DATABASE_URL in .env."
        )

    return database_url.strip()


def read_sql_file(
    file_path: Path,
) -> str:
    """
    Read and return one SQL migration file.

    Raise a clear error when the file does not exist or is empty.
    """

    if not file_path.exists():
        raise FileNotFoundError(
            f"Migration file not found: {file_path}"
        )

    sql = file_path.read_text(
        encoding="utf-8"
    ).strip()

    if not sql:
        raise RuntimeError(
            f"Migration file is empty: {file_path}"
        )

    return sql


def create_schema(
    database_url: str,
) -> None:
    """
    Apply the application schema in one transaction.

    The schema includes the call ID sequence, tables, constraints,
    and regular indexes.

    The transaction commits only when every SQL statement succeeds.
    """

    schema_sql = read_sql_file(
        INITIAL_SCHEMA_FILE
    )

    with psycopg.connect(
        database_url
    ) as connection:
        try:
            connection.execute(
                schema_sql
            )

            sequence_row = connection.execute(
                """
                SELECT sequence_name
                FROM information_schema.sequences
                WHERE
                    sequence_schema = 'public'
                    AND sequence_name = 'call_id_sequence'
                """
            ).fetchone()

            table_rows = connection.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE
                    table_schema = 'public'
                    AND table_name IN (
                        'customers',
                        'calls',
                        'transcripts'
                    )
                ORDER BY table_name
                """
            ).fetchall()

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    if sequence_row is None:
        raise RuntimeError(
            "call_id_sequence was not found after migration."
        )

    table_names = [
        row[0]
        for row in table_rows
    ]

    expected_tables = {
        "customers",
        "calls",
        "transcripts",
    }

    missing_tables = (
        expected_tables
        - set(table_names)
    )

    if missing_tables:
        raise RuntimeError(
            "Missing expected tables after migration: "
            + ", ".join(
                sorted(missing_tables)
            )
        )

    print(
        "CockroachDB schema created successfully."
    )

    print(
        "Sequence found: call_id_sequence"
    )

    print(
        "Tables found: "
        + ", ".join(table_names)
    )


def main() -> None:
    """
    Run the CockroachDB migration.
    """

    database_url = get_database_url()

    create_schema(
        database_url
    )

    print(
        "All CockroachDB migrations completed successfully."
    )


if __name__ == "__main__":
    main()