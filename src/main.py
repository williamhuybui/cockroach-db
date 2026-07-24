import random
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="cockroach-db backend")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/random")
def random_number():
    return {"number": random.randint(1, 100)}


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
