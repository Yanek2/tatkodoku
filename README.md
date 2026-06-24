# tatkodoku

Checks the Bulgarian cadastre portal (kais.cadastre.bg) once an hour for
application №`01-332521-13.05.2026` and sends an SMS the moment "Готови
документи за получаване" (ready documents) becomes non-zero.

Runs entirely on GitHub Actions (free) — no server needed. Status is
published as a static page via GitHub Pages from `docs/`.

The site blocks plain HTTP requests as bot traffic, so the checker drives
a real (stealth) headless Chromium via Playwright instead of just calling
the endpoint directly.

## One-time setup

### 1. Twilio (free trial, sends the SMS)

1. Create a free account at twilio.com — the trial includes free credit.
2. In the Twilio console, **verify the destination number** `+359894302207`
   under Phone Numbers → Verified Caller IDs (required on trial accounts —
   you can only send to numbers you've verified).
3. Get a Twilio trial phone number (Phone Numbers → Buy a number, free one
   is provided on trial).
4. Note down: **Account SID**, **Auth Token** (both on the console
   dashboard), and the **Twilio phone number** you were given.

Trial-account caveat: outgoing messages get a
"Sent from your Twilio trial account - " prefix added automatically by
Twilio. Upgrading the account (adding a small balance) removes that.

### 2. GitHub repo secrets

In the repo: Settings → Secrets and variables → Actions → New repository secret:

| Secret              | Value                                  |
|---------------------|-----------------------------------------|
| `TWILIO_ACCOUNT_SID`| from Twilio console                     |
| `TWILIO_AUTH_TOKEN` | from Twilio console                     |
| `TWILIO_FROM_NUMBER`| your Twilio number, e.g. `+1xxxxxxxxxx` |
| `NOTIFY_PHONE`      | `+359894302207`                         |

### 3. Enable GitHub Pages

Settings → Pages → Source: "Deploy from a branch" → branch `master` (or
`main`) → folder `/docs`. The dashboard will then be live at
`https://<your-username>.github.io/tatkodoku/`.

### 4. Done

The workflow (`.github/workflows/check.yml`) runs every hour automatically,
or trigger it manually any time from the Actions tab ("Run workflow").

## Local testing

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\playwright install chromium
set TWILIO_ACCOUNT_SID=...
set TWILIO_AUTH_TOKEN=...
set TWILIO_FROM_NUMBER=...
set NOTIFY_PHONE=+359894302207
venv\Scripts\python check.py
```
