---
title: Setup
description: Install gtask, create a Google OAuth client, and log in.
---

gtask talks to your account through a Google OAuth client that you create
once. After it is in place, every login is just a browser authorization that
gtask caches.

## Install

Install `gtask` as a system wide command:

```bash
git clone git@github.com:thesouldev/gtask-cli.git
cd gtask-cli
make install   # via pipx, or falls back to install.sh
```

Check it is on your PATH:

```bash
gtask --help
```

## One-time OAuth client

Do these in a browser signed in to the account that holds your tasks. The
console now calls this the Google Auth Platform.

1. Create or pick a project at the [Google Cloud console](https://console.cloud.google.com).
2. Enable the [Tasks API](https://console.cloud.google.com/apis/library/tasks.googleapis.com).
3. Open Google Auth Platform, click Get started, and fill in the app name,
   choose the External audience, and add your contact email.
4. Open Clients, create an OAuth client of type Desktop, and download its JSON.
5. Save it as `~/.config/gtask/credentials.json`.

The scope gtask requests is `https://www.googleapis.com/auth/tasks`, tasks
only. It cannot access Gmail, Drive, or Calendar.

:::tip[Publish to production]
The Tasks scope is sensitive. While the app is in Testing, Google issues a
refresh token that expires after 7 days. Set the publishing status to In
production so the token persists. Unverified is fine for personal use; you
click past one warning screen at login.
:::

## Login

```bash
gtask login
```

A browser opens once. Authorize, and the token is cached at
`~/.config/gtask/token.json`. Later commands reuse it silently.

## Configuration

gtask keeps everything under `~/.config/gtask/`:

| File | Purpose |
| --- | --- |
| `credentials.json` | the OAuth client you create once |
| `token.json` | the cached token, written after the first login |
| `ls_cache.json` | maps the numbers shown by `ls` to task ids |

Set `GTASK_CONFIG_DIR` to move that directory elsewhere. The scope is
`https://www.googleapis.com/auth/tasks`; to revoke access, delete `token.json`
and remove the app from your Google account permissions.

## Distributing to others

Each user brings their own OAuth client and runs `gtask login`. There is no
shared secret and no verification to maintain. Shipping one shared client would
require Google's verification for the sensitive Tasks scope, so bring your own
credentials is the clean path.
