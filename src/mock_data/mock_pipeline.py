import os

import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()
# Connect with database
conn = psycopg2.connect(os.getenv("DATABASE_URL"))
conn.autocommit = True
cur = conn.cursor()

#Upload number
csv_path = "mock_data.csv"
df = pd.read_csv(csv_path)

for _, row in df.iterrows():
    cur.execute(
        """
        INSERT INTO transcripts (id, call_id, "timestamp", caller_number, speaker, text, saved_to_db_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (
            row["id"],
            row["call_id"],
            row["timestamp"],
            row["caller_number"],
            row["speaker"],
            row["text"],
            row["saved_to_db_at"],
        ),
    )

print(f"Uploaded {len(df)} transcript rows from {csv_path}")
