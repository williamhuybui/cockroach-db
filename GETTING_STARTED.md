# Getting Started

Local setup for the speech assistant backend in `src/`.

## Prerequisites

- Python 3.9+
- A Twilio account and a Twilio phone number with Voice capability
- An OpenAI account with Realtime API access

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

### 3. Install dependencies

```bash
source venv/bin/activate      # macOS/Linux — see step 1 below for Windows
pip install -r requirements.txt
```

### 4. Configure environment variables

Create `.env` in the repo root with your OpenAI key:

```
OPENAI_API_KEY=your-key-here
```

Other settings (voice, greeting mode, system prompt, port, etc.) live in `src/config.py`.

## Every time you develop

Do these each time you sit down to work on the app.

### 1. Activate the virtual environment

```bash
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
```

### 2. Start ngrok

```bash
ngrok http 5050
```

Copy the `https://<subdomain>.ngrok.app` forwarding URL — you'll need it in the next step.

> Note: a free ngrok account gets a new URL every time you restart the tunnel, so you'll need to update the Twilio webhook (next step) each time too. A paid ngrok static domain avoids this.

### 3. Point your Twilio number at the ngrok URL

In the [Twilio Console](https://console.twilio.com/), open your phone number's config, set **A call comes in** to **Webhook**, and paste the ngrok URL with `/incoming-call` appended:

```
https://<subdomain>.ngrok.app/incoming-call
```

Note: if forwarding say: https://footman-frays-vowed.ngrok-free.dev. You dont need to do this step. 

### 4. Run the server

```bash
python src/main.py
```

### 5. Test it

Call your Twilio number. After the greeting, talk to the AI assistant — it responds in real time and handles interruptions (start speaking and it stops to listen).

---



** Adding tiktoken :

import tiktoken

encoding = tiktoken.get_encoding("o200k_base") # o200k_base is the encoding used by GPT-4o / gpt-realtime family models.
sample_text = "How many tokens does this sentence use?"
#Input token, output token. Input token
print(len(encoding.encode(sample_text)))