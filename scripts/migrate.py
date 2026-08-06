"""
Create CockroachDB objects required by the application.

This script performs two steps:

1. Enables CockroachDB vector-index support.
2. Applies the application schema.

The schema creates:

- call_id_sequence
- customers
- calls
- transcripts
- regular indexes
- the transcript vector index

The script reads DATABASE_URL from the repository-level .env file.
It can be rerun safely because the SQL files use IF NOT EXISTS.
"""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv


# Find the repository root.
#
# Expected structure:
#
# repository/
# ├── .env
# ├── migrations/
# │   ├── 000_enable_vector.sql
# │   └── 001_initial_schema.sql
# └── scripts/
#     └── migrate.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Enable CockroachDB vector-index support.
ENABLE_VECTOR_FILE = (
    PROJECT_ROOT
    / "migrations"
    / "000_enable_vector.sql"
)


# Create the application sequence, tables, and indexes.
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


def enable_vector_support(
    database_url: str,
) -> None:
    """
    Enable CockroachDB vector-index support.

    Cluster settings are applied separately with autocommit because
    they are not part of the normal schema transaction.
    """

    vector_sql = read_sql_file(
        ENABLE_VECTOR_FILE
    )

    with psycopg.connect(
        database_url,
        autocommit=True,
    ) as connection:
        connection.execute(
            vector_sql
        )

    print(
        "CockroachDB vector support enabled."
    )


def create_schema(
    database_url: str,
) -> None:
    """
    Apply the application schema in one transaction.

    The schema includes the call ID sequence, tables, constraints,
    regular indexes, and transcript vector index.

    The transaction commits only when every SQL statement succeeds.
    """

    schema_sql = read_sql_file(
        INITIAL_SCHEMA_FILE
    )

    with psycopg.connect(
        database_url
    ) as connection:
        try:
            # Apply the complete schema file.
            connection.execute(
                schema_sql
            )

            # Confirm the sequence was created.
            sequence_row = connection.execute(
                """
                SELECT sequence_name
                FROM information_schema.sequences
                WHERE
                    sequence_schema = 'public'
                    AND sequence_name = 'call_id_sequence'
                """
            ).fetchone()

            # Confirm the expected tables were created.
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

            # Save the schema only when every statement succeeds.
            connection.commit()

        except Exception:
            # Undo partial schema changes when the migration fails.
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
    Run all CockroachDB migration steps.
    """

    database_url = get_database_url()

    enable_vector_support(
        database_url
    )

    create_schema(
        database_url
    )

    print(
        "All CockroachDB migrations completed successfully."
    )


if __name__ == "__main__":
    main()