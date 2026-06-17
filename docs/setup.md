# Setup

gtask talks to your account through a Google OAuth client that you create
once. Google requires this client to exist; after it is in place, every login
is just a browser authorization that gtask caches.

Back to the [README](../README.md).

## One-time OAuth client

Do these steps in a browser signed in to the account that holds your tasks.

1. Create a project at https://console.cloud.google.com.
2. Enable the Tasks API:
   https://console.cloud.google.com/apis/library/tasks.googleapis.com
3. Open the OAuth consent screen. Choose the External user type and add your
   tasks account as a test user.
4. Go to Credentials, choose Create credentials, then OAuth client ID. Pick
   the Desktop application type and create it.
5. Download the client JSON and save it as
   `~/.config/gtask/credentials.json`.

The scope gtask requests is `https://www.googleapis.com/auth/tasks`, which
covers tasks only. It cannot access Gmail, Drive, or Calendar.

## Login

```bash
gtask login
```

A browser window opens once. Authorize the access, and the token is written to
`~/.config/gtask/token.json`. Later commands reuse it silently and refresh it
when it expires, so you should not need to log in again.

If you ever move the config directory, set `GTASK_CONFIG_DIR`. See
[configuration](configuration.md).

## Troubleshooting

- `No OAuth client found`: the `credentials.json` file is missing or in the
  wrong place. Repeat step 5 above.
- The browser shows an unverified app warning: expected for a personal client.
  Continue past it for your own test-user account.
- Wrong account: the account you pick in the browser is the one gtask manages.
  Delete `~/.config/gtask/token.json` and run `gtask login` again to switch.
