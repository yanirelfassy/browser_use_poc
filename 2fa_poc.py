"""
POC: Browser-Use Cloud with 2FA handling + persistent profile.

Flow:
  Run 1 → create a cloud profile → agent opens login page and pauses
          → user logs in manually via liveUrl (credentials + 2FA)
          → a snapshot task runs to persist the session into the profile
  Run 2 → same profile loaded → already logged in → agent goes straight to task
"""

import os
from dotenv import load_dotenv
from browser_use_sdk import BrowserUse

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

TARGET_URL  = "https://gmail.com"
TARGET_TASK = "login to the gmail account and tell me what is the latest email in the inbox title"

# Store the profile ID after first run so we can reuse it.
PROFILE_ID_FILE = "profile_id.txt"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_profile_id() -> str | None:
    """Load a previously saved profile ID from disk."""
    if os.path.exists(PROFILE_ID_FILE):
        with open(PROFILE_ID_FILE) as f:
            return f.read().strip() or None
    return None


def save_profile_id(profile_id: str):
    """Persist the profile ID for future runs."""
    with open(PROFILE_ID_FILE, "w") as f:
        f.write(profile_id)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    client = BrowserUse(api_key=os.environ["BROWSER_USE_API_KEY"])

    profile_id = load_profile_id()
    first_run = profile_id is None

    # ── First run: create a profile ───────────────────────────────────────
    if first_run:
        profile = client.profiles.create_profile(name="2FA POC Profile")
        profile_id = profile.id
        save_profile_id(profile_id)
        print(f"Created new profile: {profile_id}")
    else:
        print(f"Reusing saved profile: {profile_id}")

    # ── Create a session with the profile (inherits saved cookies) ────────
    session = client.sessions.create_session(profile_id=profile_id)
    print(f"Session created: {session.id}")
    print(f"Live view: {session.live_url}")

    # ── First run: let the user log in manually ───────────────────────────
    if first_run:
        # Navigate to the login page.
        nav_task = client.tasks.create_task(
            session_id=session.id,
            task=f"Go to {TARGET_URL} and stop. Do not try to log in.",
            llm="browser-use-llm",
        )
        nav_task.complete()

        print("\n" + "=" * 60)
        print("  MANUAL LOGIN REQUIRED")
        print(f"  1. Open the live view: {session.live_url}")
        print("  2. Log in with your credentials and complete 2FA.")
        print("  3. Come back here and press ENTER when done.")
        print("=" * 60 + "\n")

        input("  Press ENTER after you've logged in successfully...")

        # Run a snapshot task so the profile captures the authenticated state.
        # Profile state is saved when a task completes within the session.
        print("  Saving session to profile...")
        snapshot = client.tasks.create_task(
            session_id=session.id,
            task="Do nothing. Just confirm the current page URL and title.",
            llm="browser-use-llm",
            max_steps=3,
        )
        snapshot.complete()
        print("  Profile saved!\n")

    # ── Now run the actual task (already authenticated) ───────────────────
    task = client.tasks.create_task(
        session_id=session.id,
        task=f"You are already logged in to {TARGET_URL}. {TARGET_TASK}",
        llm="browser-use-llm",
    )

    result = task.complete()
    print(f"\nResult: {result.output}")

    # ── Cleanup: stop the session (profile state is already saved) ────────
    client.sessions.update_session(session.id, action="stop")
    print("\nDone! Run the script again - login will be skipped.")


if __name__ == "__main__":
    main()
