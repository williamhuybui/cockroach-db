# cockroach-db

Team repo for the [CockroachDB × AWS Hackathon — Build with Agentic Memory](https://cockroachdb-ai.devpost.com/) (deadline Aug 18, 2026). Goal: build an agentic app using CockroachDB as persistent memory (≥2 CockroachDB tools: MCP Server, Distributed Vector Indexing, ccloud CLI, Agent Skills Repo) deployed on AWS (≥1 AWS service, e.g. Bedrock, Lambda, S3).

## Backend (FastAPI)

### 1. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
```

### 2. Install dependencies

```bash
pip install -r src/requirements.txt
```

### 3. Run the server

From the repo root:

```bash
uvicorn src.main:app --reload
```

### 4. Open it in your browser

Visit **http://127.0.0.1:8000/** — do not open `src/static/index.html` directly as a file, it needs to be served by the backend to fetch data.

- http://127.0.0.1:8000/ — HTML page showing a random number
- http://127.0.0.1:8000/health — health check
- http://127.0.0.1:8000/docs — Swagger API docs

### 5. Deactivate the virtual environment when done

```bash
deactivate
```