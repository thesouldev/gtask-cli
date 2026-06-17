# Configuration

gtask keeps everything under one directory and needs no config file.

Back to the [README](../README.md).

## Files

All paths are under `~/.config/gtask/` by default.

| File                | Purpose                                          |
| ------------------- | ------------------------------------------------ |
| `credentials.json`  | the OAuth client you create once (see setup)     |
| `token.json`        | the cached token, written after the first login  |
| `ls_cache.json`     | maps the numbers shown by `ls` to real task ids  |

The `credentials.json` and `token.json` paths are shared by design with the
future `gtask-mcp` server, so a single login serves both tools.

## Environment

| Variable           | Effect                                              |
| ------------------ | --------------------------------------------------- |
| `GTASK_CONFIG_DIR` | move the config directory off the default location  |
| `GTASK_BIN_DIR`    | where `install.sh` links the `gtask` command        |

Example:

```bash
export GTASK_CONFIG_DIR="$HOME/.gtask"
```

## Security

The OAuth scope is `https://www.googleapis.com/auth/tasks`, tasks only. The
token cannot read or change Gmail, Drive, or Calendar. To revoke access,
delete `token.json` and remove the app from your Google account permissions.
