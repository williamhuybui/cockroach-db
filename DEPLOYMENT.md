# Production Deployment Guide

This guide explains how to deploy the Front Desk application to Amazon Lightsail and configure GitHub Actions to deploy future changes automatically.

The deployment uses:

- Amazon Lightsail
- Ubuntu
- Python virtual environment
- systemd
- Caddy
- `sslip.io`
- GitHub Actions
- Twilio

Docker and ngrok are not required.

## Deployment flow

```text
Developer writes code
  -> pushes a development branch
  -> opens a pull request into main
  -> GitHub Actions checks the code
  -> pull request is merged
  -> GitHub Actions connects to Lightsail
  -> Lightsail downloads the latest main branch
  -> dependencies are installed
  -> the application restarts
  -> a health check confirms the deployment
```

Application requests follow this flow:

```text
Twilio
  -> HTTPS webhook
  -> Caddy
  -> FastAPI
  -> OpenAI Realtime
  -> CockroachDB
```

## Required values

Before starting, collect these values:

```text
GITHUB_REPOSITORY_URL
LIGHTSAIL_STATIC_IP
SSLIP_HOSTNAME
OPENAI_API_KEY
DATABASE_URL
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_PHONE_NUMBER
GROQ_API_KEY
```

The `sslip.io` hostname is created from the Lightsail static IP.

Replace the dots in the IP address with dashes and add `.sslip.io`:

```text
<LIGHTSAIL_STATIC_IP_WITH_DASHES>.sslip.io
```

No domain registration is required.

## 1. Create the Lightsail instance

Create an Ubuntu Lightsail instance.

A 2 GB Linux instance is a practical starting point for this application.

After creating the instance:

1. Attach a static IP.
2. Record the static IP.
3. Open the Networking tab.
4. Configure the firewall.

Required inbound firewall rules:

| Application | Protocol | Port | Source |
| --- | --- | --- | --- |
| HTTP | TCP | 80 | Any IP |
| HTTPS | TCP | 443 | Any IP |
| SSH | TCP | 22 | Trusted administrator IPs |

## 2. Connect to Lightsail

Open the Lightsail browser SSH terminal.

Update the server and install the required software:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip caddy
```

## 3. Create the application user

Create a dedicated account for running the application:

```bash
sudo useradd --system --create-home --shell /bin/bash frontdesk
sudo install -d -o frontdesk -g frontdesk /opt/frontdesk
```

The application will run as `frontdesk`, not as `root`.

## 4. Clone the repository

Clone the repository into `/opt/frontdesk`:

```bash
sudo -u frontdesk git clone <GITHUB_REPOSITORY_URL> /opt/frontdesk
```

Select the production branch:

```bash
sudo -u frontdesk git -C /opt/frontdesk checkout main
```

GitHub remains the main source of code.

The copy inside `/opt/frontdesk` is the version that runs on Lightsail.

## 5. Create the Python environment

Create a virtual environment:

```bash
sudo -u frontdesk python3 -m venv /opt/frontdesk/.venv
```

Upgrade pip:

```bash
sudo -u frontdesk /opt/frontdesk/.venv/bin/python -m pip install --upgrade pip
```

Install the dependencies:

```bash
sudo -u frontdesk /opt/frontdesk/.venv/bin/python \
  -m pip install \
  -r /opt/frontdesk/requirements.txt
```

## 6. Create the production environment file

Create:

```bash
sudo nano /etc/frontdesk.env
```

Add:

```dotenv
OPENAI_API_KEY=<OPENAI_API_KEY>
DATABASE_URL=<DATABASE_URL>
TWILIO_ACCOUNT_SID=<TWILIO_ACCOUNT_SID>
TWILIO_AUTH_TOKEN=<TWILIO_AUTH_TOKEN>
TWILIO_PHONE_NUMBER=<TWILIO_PHONE_NUMBER>
GROQ_API_KEY=<GROQ_API_KEY>
LOG_LEVEL=INFO
```

Rules:

- Do not add spaces around `=`.
- Use one variable per line.
- Do not put this file in GitHub.
- Do not place these application secrets in the GitHub Actions workflow.

Protect the file:

```bash
sudo chown root:frontdesk /etc/frontdesk.env
sudo chmod 640 /etc/frontdesk.env
```

## 7. Create the systemd service

Create:

```bash
sudo nano /etc/systemd/system/frontdesk.service
```

Add:

```ini
[Unit]
Description=Front Desk FastAPI application
After=network-online.target
Wants=network-online.target

[Service]
User=frontdesk
Group=frontdesk
WorkingDirectory=/opt/frontdesk
EnvironmentFile=/etc/frontdesk.env
ExecStart=/opt/frontdesk/.venv/bin/uvicorn main:app --app-dir /opt/frontdesk/src --host 127.0.0.1 --port 5050
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Load the service:

```bash
sudo systemctl daemon-reload
```

Enable it at startup:

```bash
sudo systemctl enable frontdesk
```

Start it:

```bash
sudo systemctl start frontdesk
```

Check its status:

```bash
sudo systemctl status frontdesk --no-pager
```

Test FastAPI directly:

```bash
curl http://127.0.0.1:5050/health
```

Expected response:

```json
{
  "application": "healthy",
  "database": "connected"
}
```

View logs:

```bash
sudo journalctl -u frontdesk -n 50 --no-pager
```

Follow live logs:

```bash
sudo journalctl -u frontdesk -f
```

## 8. Create the sslip.io hostname

Convert the Lightsail static IP into an `sslip.io` hostname:

```text
<LIGHTSAIL_STATIC_IP_WITH_DASHES>.sslip.io
```

Save this hostname. It will be used for:

- Caddy
- Twilio
- Public health checks

Verify it from the local computer:

```powershell
nslookup <SSLIP_HOSTNAME>
```

The returned address must match the Lightsail static IP.

## 9. Configure Caddy

Edit:

```bash
sudo nano /etc/caddy/Caddyfile
```

Add:

```caddyfile
<SSLIP_HOSTNAME> {
    reverse_proxy 127.0.0.1:5050
}
```

Validate the configuration:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
```

Enable Caddy:

```bash
sudo systemctl enable caddy
```

Restart Caddy:

```bash
sudo systemctl restart caddy
```

Check its status:

```bash
sudo systemctl status caddy --no-pager
```

Test the public endpoint from the local computer:

```powershell
curl.exe -i https://<SSLIP_HOSTNAME>/health
```

The result should contain:

```text
HTTP/1.1 200 OK
```

## 10. Configure Twilio

Open the Twilio phone number configuration.

Set the incoming-call webhook to:

```text
https://<SSLIP_HOSTNAME>/incoming-call
```

Select:

```text
HTTP POST
```

Leave the fallback URL empty unless there is a second working deployment.

Leave the status callback empty unless the application has a dedicated status-callback endpoint.

Save the phone-number configuration.

The application uses these routes:

| Route | Purpose |
| --- | --- |
| `/health` | Tests the application and database |
| `/incoming-call` | Receives incoming Twilio calls |
| `/media-stream` | Receives Twilio audio through WebSocket |

Twilio receives TwiML from `/incoming-call` and then connects to:

```text
wss://<SSLIP_HOSTNAME>/media-stream
```

## 11. Create the server deployment script

Create:

```bash
sudo nano /usr/local/sbin/deploy-frontdesk
```

Add:

```bash
#!/usr/bin/env bash
set -e

APP_DIR="/opt/frontdesk"

echo "Downloading the latest code..."
sudo -u frontdesk git -C "$APP_DIR" checkout main
sudo -u frontdesk git -C "$APP_DIR" pull --ff-only origin main

echo "Installing dependencies..."
sudo -u frontdesk "$APP_DIR/.venv/bin/python" \
  -m pip install \
  -r "$APP_DIR/requirements.txt"

echo "Restarting the application..."
systemctl restart frontdesk

echo "Checking the application..."
sleep 5
curl --fail http://127.0.0.1:5050/health

echo
echo "Deployment completed successfully."
```

Make it executable:

```bash
sudo chmod 755 /usr/local/sbin/deploy-frontdesk
```

Test it manually:

```bash
sudo /usr/local/sbin/deploy-frontdesk
```

Do not continue until the manual deployment succeeds.

## 12. Create the GitHub Actions deployment user

Create a dedicated deployment account:

```bash
sudo adduser --disabled-password --gecos "" deploy
```

Create its SSH directory:

```bash
sudo install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
sudo touch /home/deploy/.ssh/authorized_keys
sudo chown deploy:deploy /home/deploy/.ssh/authorized_keys
sudo chmod 600 /home/deploy/.ssh/authorized_keys
```

## 13. Create the deployment SSH key

Run this on the developer’s local computer:

```powershell
ssh-keygen -t ed25519 `
  -f "$env:USERPROFILE\.ssh\frontdesk_github_actions" `
  -C "github-actions-frontdesk"
```

Leave the passphrase empty.

This creates:

```text
frontdesk_github_actions
frontdesk_github_actions.pub
```

The file without `.pub` is the private key.

The `.pub` file is the public key.

Display the public key:

```powershell
Get-Content "$env:USERPROFILE\.ssh\frontdesk_github_actions.pub"
```

Copy the public-key line into:

```text
/home/deploy/.ssh/authorized_keys
```

Do not put the private key in `authorized_keys`.

## 14. Allow the deployment command

Create:

```bash
sudo nano /etc/sudoers.d/frontdesk-deploy
```

Add:

```sudoers
deploy ALL=(root) NOPASSWD: /usr/local/sbin/deploy-frontdesk
```

Protect and validate the file:

```bash
sudo chmod 440 /etc/sudoers.d/frontdesk-deploy
sudo visudo -cf /etc/sudoers.d/frontdesk-deploy
```

## 15. Create the GitHub Actions secrets

Open:

```text
GitHub repository
  -> Settings
  -> Secrets and variables
  -> Actions
```

Create:

| Secret | Value |
| --- | --- |
| `LIGHTSAIL_HOST` | Lightsail static IP |
| `LIGHTSAIL_USER` | `deploy` |
| `LIGHTSAIL_SSH_KEY` | Complete private deployment key |
| `LIGHTSAIL_KNOWN_HOSTS` | Lightsail public SSH host key |

### LIGHTSAIL_SSH_KEY

Validate the private key locally:

```powershell
$keyPath = "$env:USERPROFILE\.ssh\frontdesk_github_actions"
ssh-keygen -y -f $keyPath
```

Copy it:

```powershell
Get-Content -Raw $keyPath | Set-Clipboard
```

Paste it into `LIGHTSAIL_SSH_KEY`.

The value must include:

```text
-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
```

### LIGHTSAIL_KNOWN_HOSTS

Run this from the trusted Lightsail browser SSH terminal:

```bash
sudo cat /etc/ssh/ssh_host_ed25519_key.pub
```

Create the secret in this format:

```text
<LIGHTSAIL_STATIC_IP> ssh-ed25519 <SERVER_PUBLIC_HOST_KEY>
```

Do not include:

- `https://`
- `/32`
- Quotation marks
- The comment at the end of the public key

## 16. Create the GitHub Actions workflow

Create:

```text
.github/workflows/deploy.yml
```

Add:

```yaml
name: CI/CD

on:
  pull_request:
    branches:
      - main

  push:
    branches:
      - main

permissions:
  contents: read

jobs:
  check:
    name: Check code
    runs-on: ubuntu-latest

    steps:
      - name: Download code
        uses: actions/checkout@v6

      - name: Install Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Check Python files
        run: python -m compileall -q src scripts

  deploy:
    name: Deploy to Lightsail
    if: github.event_name == 'push'
    needs: check
    runs-on: ubuntu-latest

    concurrency:
      group: frontdesk-production
      cancel-in-progress: false

    steps:
      - name: Configure SSH
        env:
          SSH_PRIVATE_KEY: ${{ secrets.LIGHTSAIL_SSH_KEY }}
          SSH_KNOWN_HOSTS: ${{ secrets.LIGHTSAIL_KNOWN_HOSTS }}
        run: |
          install -m 700 -d ~/.ssh
          printf '%s\n' "$SSH_PRIVATE_KEY" | tr -d '\r' > ~/.ssh/id_ed25519
          printf '%s\n' "$SSH_KNOWN_HOSTS" > ~/.ssh/known_hosts
          chmod 600 ~/.ssh/id_ed25519
          chmod 600 ~/.ssh/known_hosts

      - name: Deploy
        env:
          DEPLOY_HOST: ${{ secrets.LIGHTSAIL_HOST }}
          DEPLOY_USER: ${{ secrets.LIGHTSAIL_USER }}
        run: |
          ssh \
            -o BatchMode=yes \
            -o IdentitiesOnly=yes \
            -o StrictHostKeyChecking=yes \
            "$DEPLOY_USER@$DEPLOY_HOST" \
            "sudo -n /usr/local/sbin/deploy-frontdesk"
```

## 17. Deployment process

For every change:

1. Create or update a development branch.
2. Test the change locally.
3. Push the branch to GitHub.
4. Open a pull request into `main`.
5. Wait for the code check to pass.
6. Review the pull request.
7. Merge it into `main`.
8. Open the GitHub Actions tab.
9. Confirm **Check code** passes.
10. Confirm **Deploy to Lightsail** passes.
11. Test the production application.

Development branches do not deploy.

Only changes merged into `main` deploy to Lightsail.

## 18. End-to-end test

### Test HTTPS

```powershell
curl.exe -i https://<SSLIP_HOSTNAME>/health
```

Expected result:

```text
HTTP/1.1 200 OK
```

### Test the server

```bash
sudo systemctl is-active frontdesk caddy
sudo systemctl is-enabled frontdesk caddy
```

Both services should be active and enabled.

### Check the deployed commit

```bash
sudo -u frontdesk git -C /opt/frontdesk branch --show-current
sudo -u frontdesk git -C /opt/frontdesk log -1 --oneline
sudo -u frontdesk git -C /opt/frontdesk status --short
```

The deployed commit should match the latest commit on `main`.

### Test Twilio

Follow the logs:

```bash
sudo journalctl -u frontdesk -f
```

Call the Twilio number and confirm:

1. The greeting plays.
2. The call remains connected.
3. The assistant answers a question.
4. The call data reaches CockroachDB.

## 19. Common errors

### Host key verification failed

Confirm that `LIGHTSAIL_KNOWN_HOSTS` uses the same IP as `LIGHTSAIL_HOST`.

Required format:

```text
<LIGHTSAIL_STATIC_IP> ssh-ed25519 <SERVER_PUBLIC_HOST_KEY>
```

### Error in libcrypto

Confirm that `LIGHTSAIL_SSH_KEY` contains the complete private key.

Keep this line in the workflow:

```bash
printf '%s\n' "$SSH_PRIVATE_KEY" | tr -d '\r' > ~/.ssh/id_ed25519
```

It removes Windows carriage-return characters.

### Permission denied publickey

Confirm that the public key matching `LIGHTSAIL_SSH_KEY` exists in:

```text
/home/deploy/.ssh/authorized_keys
```

### Twilio error 11200

Check:

- The webhook on the actual Twilio phone number
- The public hostname
- `/incoming-call`
- Caddy
- FastAPI logs
- Whether an old ngrok URL remains configured

### Twilio error 31901

Check:

- Port 443
- Caddy
- HTTPS
- The TLS certificate
- `/media-stream`
- The secure WebSocket URL

## 20. Security rules

- Never commit `.env` files.
- Never commit SSH private keys.
- Store application secrets only on the server.
- Store deployment secrets only in GitHub Actions Secrets.
- Use separate application and deployment users.
- Keep strict SSH host verification enabled.
- Do not edit production code directly in `/opt/frontdesk`.
- Rotate credentials exposed in screenshots, commits, or messages.
- Protect the dashboard and sensitive API routes before storing real customer data.