"""Run a query against CockroachDB and print it as a pandas DataFrame.

Usage:
    python scripts/query.py                                 # default query
    python scripts/query.py "SELECT * FROM calls"
    python scripts/query.py "SELECT * FROM customers WHERE phone_number = %s" "+14175551001"
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from database import execute_sql

sql = sys.argv[1] if len(sys.argv) > 1 else "SELECT * FROM customers"
params = tuple(sys.argv[2:]) or None

df = pd.DataFrame(execute_sql(sql, params))
print(df.columns.tolist())
print(df)
