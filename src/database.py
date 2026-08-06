"""
Shared CockroachDB connection management for FastAPI.

This file manages one reusable database connection pool:

1. main.py passes DATABASE_URL into configure_database().
2. The pool is created but remains closed.
3. FastAPI opens the pool when the application starts.
4. API routes borrow connections from the shared pool.
5. Transactions commit when successful.
6. Transactions roll back when an error occurs.
7. FastAPI closes the pool when the application stops.

The pool avoids opening a new CockroachDB connection for every API request and allows for multiple concurrent API requests.
"""

from contextlib import asynccontextmanager

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


# Store the single shared database pool.
#
# It begins as None because main.py must provide DATABASE_URL before
# the application can connect to CockroachDB.
database_pool: AsyncConnectionPool | None = None


def configure_database(
    database_url: str,
) -> AsyncConnectionPool:
    """
    Create and return the shared CockroachDB connection pool.

    DATABASE_URL contains the database host, credentials, database
    name, and SSL settings.

    The pool is created only once. main.py opens it during FastAPI
    startup.
    """

    global database_pool

    if not database_url:
        raise ValueError(
            "DATABASE_URL cannot be empty."
        )

    # Create the pool only when it has not already been configured.
    if database_pool is None:
        database_pool = AsyncConnectionPool(
            # Use DATABASE_URL for all CockroachDB connections.
            conninfo=database_url,

            # Keep one connection ready for API requests.
            min_size=1,

            # Allow up to three concurrent database connections.
            max_size=3,

            # main.py opens the pool when FastAPI starts.
            open=False,

            # Return query rows as dictionaries.
            #
            # Example:
            # row["caller_number"]
            #
            # Instead of:
            # row[0]
            kwargs={
                "row_factory": dict_row,
            },
        )

    return database_pool


def get_database_pool() -> AsyncConnectionPool:
    """
    Return the configured database pool.

    Raise a clear error when main.py has not configured the pool.
    """

    if database_pool is None:
        raise RuntimeError(
            "Database is not configured. "
            "Call configure_database(DATABASE_URL) "
            "in main.py."
        )

    return database_pool


@asynccontextmanager
async def get_database_connection():
    """
    Borrow one CockroachDB connection from the shared pool.

    The connection returns to the pool automatically when the API
    operation finishes.
    """

    pool = get_database_pool()

    async with pool.connection() as connection:
        yield connection


@asynccontextmanager
async def get_database_transaction():
    """
    Run database statements inside one transaction.

    Successful operations are committed automatically.

    Failed operations are rolled back automatically, preventing
    partially saved transcript, call, or customer records.
    """

    async with get_database_connection() as connection:
        async with connection.transaction():
            yield connection