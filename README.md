# Browser-Use Cloud — 2FA Persistent Login POC

Proof of concept for using [Browser-Use Cloud](https://docs.cloud.browser-use.com) to automate browser tasks on sites that require login + two-factor authentication, without ever handling user credentials in code.

## How it works

### First run — manual login

1. The script creates a **cloud Profile** (a persistent browser identity).
2. A browser session opens and navigates to the target URL.
3. The user receives a **live URL** to the cloud browser.
4. The user logs in manually — typing credentials and completing 2FA directly in the browser. **The application never sees the password.**
5. After the user confirms login, a snapshot task runs to persist the authenticated state (cookies, localStorage, tokens) into the profile.

### Subsequent runs — login skipped

1. The same profile is loaded from `profile_id.txt`.
2. A new session is created with that profile — it inherits all saved cookies.
3. The target site recognizes the session and skips login entirely.
4. The agent goes straight to the task.

```
Run 1:  create profile → open browser → USER logs in → session saved to profile
Run 2+: load profile  → open browser → already logged in → run task
```

## Setup

### Prerequisites

- Python 3.10+
- A [Browser-Use Cloud](https://cloud.browser-use.com) account and API key

### Install dependencies

```bash
pip install browser-use-sdk python-dotenv
```

### Environment variables

Create a `.env` file in the project root:

```env
BROWSER_USE_API_KEY=bu_your_api_key_here
```

| Variable | Required | Description |
|----------|----------|-------------|
| `BROWSER_USE_API_KEY` | Yes | Your Browser-Use Cloud API key. Get it from the [dashboard](https://cloud.browser-use.com). |

### Configuration

Edit the constants at the top of `2fa_poc.py`:

```python
TARGET_URL  = "https://gmail.com"                  # The site to automate
TARGET_TASK = "Tell me the latest email subject"   # What the agent should do after login
```

### Run

```bash
python 2fa_poc.py
```

On first run you'll see a live URL — open it in your browser to log in manually.

## File structure

```
.
├── 2fa_poc.py        # Main script
├── .env              # API key (gitignored)
├── .gitignore
├── profile_id.txt    # Saved profile ID after first run (gitignored)
└── README.md
```

## Security model

### Credentials are never in your code

The user types their username, password, and 2FA code directly into the cloud browser via the live URL. At no point does the application read, transmit, or store credentials. The only thing persisted is the resulting session state (cookies and tokens) inside the Browser-Use Cloud profile.

### What is stored in the cloud profile

- Session cookies
- localStorage / sessionStorage data
- Authentication tokens set by the target site
- Browser form data

This is equivalent to what a normal browser stores when you check "Remember me". No raw passwords are saved.

### What is stored locally

- `profile_id.txt` — a UUID referencing the cloud profile. Contains no credentials.
- `.env` — your Browser-Use API key. Gitignored.

### Data in transit

All communication with Browser-Use Cloud is over HTTPS. The live URL for manual login is also served over HTTPS/WSS.

## Data deletion

Profile data persists in Browser-Use Cloud **indefinitely** until explicitly deleted. There is no auto-expiry.

### Deleting a user's data

To remove all stored session data for a user:

```python
from browser_use_sdk import BrowserUse

client = BrowserUse(api_key="bu_...")

# Delete the cloud profile — removes all cookies, tokens, and saved state
client.profiles.delete_browser_profile(profile_id="the-profile-id")
```

This is a single API call. Once executed:
- All cookies and authentication tokens are removed from the cloud.
- The profile ID becomes invalid.
- The user will need to log in manually again on the next run.

To also clean up sessions and their task history:

```python
client.sessions.delete_session(session_id="the-session-id")
```

### Local cleanup

Delete `profile_id.txt` to force a fresh first-run flow.

```bash
rm profile_id.txt
```

## Production considerations

### Session expiry

Cloud profiles don't auto-expire, but the **target site's cookies do**. If a session cookie expires (e.g., after 7-30 days depending on the site), the profile will still exist but the login will no longer be valid. Your application should handle this by:

- Detecting when the agent lands on a login page during a "subsequent run"
- Triggering the manual login flow again
- Refreshing profiles proactively for long-lived users

### Profile limits by plan

| Plan | Max profiles |
|------|-------------|
| Free | 2 |
| Developer | 5 |
| Business | Unlimited |
| Scaleup | Unlimited |

### Multi-user production architecture

For production with many users, store the profile ID per user in your database:

```
users table
├── user_id
├── email
└── browser_profile_id  ← UUID from Browser-Use Cloud
```

Each user gets their own isolated profile. Profiles have no cross-contamination — one user's cookies are never visible to another.

### Credential security (if ever needed)

This POC avoids storing credentials entirely. If a future requirement demands storing usernames/passwords (e.g., for fully automated re-login), use:

- **Encryption at rest** — AES-256 via a cloud KMS (AWS KMS, GCP Cloud KMS, HashiCorp Vault)
- **Never store plaintext** — encrypt before writing to your database, decrypt only in memory at the moment of use
- **Key separation** — the encryption key lives in the KMS, not alongside the encrypted data

### GDPR / data privacy

- User credentials are never collected or stored by this application.
- Session data in the cloud profile can be fully deleted via `delete_browser_profile()`.
- For GDPR compliance, call this endpoint when a user requests data deletion.
- Browser-Use Cloud processes data on their infrastructure — review their [terms](https://browser-use.com) for your DPA requirements.
