"""Create the database tables by running every .sql file in migrations/.

Files run in filename order, so the number prefix controls dependency order.
Everything uses IF NOT EXISTS, so re-running is safe. See migrations/README.md.

Usage:
    python scripts/migrate.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from database import execute_sql

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "migrations")

sql_files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql"))
if not sql_files:
    sys.exit(f"No .sql files found in {MIGRATIONS_DIR}")

for filename in sql_files:
    with open(os.path.join(MIGRATIONS_DIR, filename), encoding="utf-8") as f:
        execute_sql(f.read())
    print(f"applied {filename}")

print("\nTables now in the database:")
for row in execute_sql(
    """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
    """
):
    print(" ", row["table_name"])
