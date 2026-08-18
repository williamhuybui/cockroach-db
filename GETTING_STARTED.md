# Getting Started

Local setup for the speech assistant backend in `src/`.

## Prerequisites

- Python 3.9+
- A Twilio account and a Twilio phone number with Voice capability
- An OpenAI account with Realtime API access
- A CockroachDB Cloud cluster (ask Ha for access if you don't have credentials)

## One-time setup

Do these once per machine (skip anything you've already done).

### 1. Install ngrok

```bash
brew install ngrok        # macOS
```
Sign in with cockroachsurvival@gmail.com

Follow the instruction here: 
https://dashboard.ngrok.com/get-started/setup/mac-os

### 2. Create a virtual environment

```bash
python3 -m venv venv
```

> **Windows + WSL:** if you're developing inside VS Code's WSL terminal (bash prompt, even though the project folder is under `C:\Users\...`), run this command inside that WSL terminal — not PowerShell/Command Prompt. A venv created by Windows Python and one created by WSL Python aren't interchangeable; mixing them causes `command not found` when activating.

### 3. Install dependencies

```bash
source venv/bin/activate      # macOS/Linux/WSL — see step 1 below for native Windows
pip install -r requirements.txt
```

### 4. Configure environment variables

Create `.env` in the repo root. **Never commit this file** — it's already in `.gitignore`, but double-check with `git status` before your first commit.

```dotenv
OPENAI_API_KEY="your-openai-api-key-here"
GROQ_API_KEY="your-groq-api-key-here"

DATABASE_URL="postgresql://<user>:<password>@<cluster-host>:26257/defaultdb?sslmode=verify-full"

TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_AUTH_TOKEN="your-twilio-auth-token"
TWILIO_PHONE_NUMBER="+1XXXXXXXXXX"
```

Where to get each value:

| Variable | Where |
|---|---|
| `OPENAI_API_KEY` | platform.openai.com → API keys |
| `GROQ_API_KEY` | console.groq.com → API Keys |
| `DATABASE_URL` | CockroachDB Cloud console → cluster → **Connect** button → connection string (ask Ha for cluster access if you don't have it) |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | Twilio Console → **Account** → API keys & tokens |
| `TWILIO_PHONE_NUMBER` | Twilio Console → **Phone Numbers → My Inventory** — the project's number, currently `+18326481907` |

If `DATABASE_URL` fails with `root certificate file ... does not exist` or `SSL error: certificate verify failed`, download the cluster's CA cert once per machine:
```bash
mkdir -p ~/.postgresql
curl -o ~/.postgresql/root.crt <CA cert URL from CockroachDB Cloud → cluster → Connect>
```

#### Optional: Google Calendar (appointment scheduling)

The dashboard's "Schedule" button (see `src/calendar_service.py`) works without
this — appointments just save to the `tasks` table without a calendar event.
To have them show up on a real Google Calendar too:

1. In [Google Cloud Console](https://console.cloud.google.com/), create/select a project and enable the **Google Calendar API**.
2. **IAM & Admin → Service Accounts** → create one → **Keys → Add key → Create new key (JSON)**. Save the downloaded file as `google-service-account.json` in the repo root (already gitignored).
3. Open the Google Calendar you want appointments on → **Settings and sharing → Share with specific people** → add the service account's `client_email` (from the JSON key) with **"Make changes to events"**. Then copy that calendar's ID from **Settings and sharing → Integrate calendar**.
4. Add to `.env`:
   ```dotenv
   GOOGLE_CALENDAR_ID="your-calendar-id@group.calendar.google.com"
   GOOGLE_SERVICE_ACCOUNT_FILE="google-service-account.json"
   ```
   (Relative paths resolve against the repo root regardless of where you run things from — see `src/calendar_service.py`.)
5. Sanity-check it directly: `cd src && python calendar_service.py` — it creates a test event a day out and prints its id.

The company's local timezone used to interpret the Schedule sheet's date/time
is `COMPANY_TIMEZONE` in `src/config.py` (defaults to `"America/Los_Angeles"`).

Other settings (voice, greeting mode, system prompt, port, VAD type, call length limits) live in `src/config.py`.

## Every time you develop

Do these each time you sit down to work on the app.

### 1. Activate the virtual environment

```bash
source venv/bin/activate      # macOS/Linux/WSL
venv\Scripts\activate         # native Windows (Command Prompt/PowerShell only)
```

### 2. Start ngrok

```bash
ngrok http 5050
```

Copy the `https://<subdomain>.ngrok.app` forwarding URL — you'll need it in the next step.

> Note: a free ngrok account gets a new URL every time you restart the tunnel, so you'll need to update the Twilio webhook (next step) each time too. A paid ngrok static domain avoids this.
>
> If ngrok fails with `ERR_NGROK_334` ("endpoint already online"), someone else on the team is already running a tunnel on the shared static domain — check `dashboard.ngrok.com/endpoints` or ask in the team channel before force-stopping it.

### 3. Point your Twilio number at the ngrok URL

In the [Twilio Console](https://console.twilio.com/), open your phone number's config, set **A call comes in** to **Webhook**, and paste the ngrok URL with `/incoming-call` appended: https://<subdomain>.ngrok.app/incoming-call

Note: if forwarding shows `https://footman-frays-vowed.ngrok-free.dev`, you don't need to do this step — the number is already pointed at that static domain.

### 4. Run the server

```bash
python src/main.py
```

Check the startup log for `Application startup complete.` with no `WARNING psycopg.pool` lines — that confirms the CockroachDB connection is good before you make a test call.

### 5. Test it

Call your Twilio number. After the greeting, talk to the AI assistant — it responds in real time and handles interruptions (start speaking and it stops to listen).

---



** Adding tiktoken :

import tiktoken

encoding = tiktoken.get_encoding("o200k_base") # o200k_base is the encoding used by GPT-4o / gpt-realtime family models.
sample_text = "How many tokens does this sentence use?"
#Input token, output token. Input token
print(len(encoding.encode(sample_text)))
