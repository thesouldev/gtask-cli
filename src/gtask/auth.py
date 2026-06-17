"""
OAuth login and token caching.

First run opens the browser for consent, then caches the token so later runs
are silent. Refreshes automatically when the access token expires.
"""

from __future__ import annotations

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from . import config


def get_credentials() -> Credentials:
    creds = None
    if config.TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(
            str(config.TOKEN_FILE), config.SCOPES
        )

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not config.CREDENTIALS_FILE.exists():
            raise SystemExit(
                f"No OAuth client found at {config.CREDENTIALS_FILE}.\n"
                "Run the one-time setup: enable the Tasks API, create a "
                "Desktop OAuth client, and save its JSON there."
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(config.CREDENTIALS_FILE), config.SCOPES
        )
        creds = flow.run_local_server(port=0)

    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config.TOKEN_FILE.write_text(creds.to_json())
    return creds
