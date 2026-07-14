# AStock Lens Desktop

Standalone Electron + React client for the personal stock diagnosis product track.

This app intentionally does not reuse the current `web/` information architecture. It keeps the product surface focused on one workflow:

1. User asks about one stock from the bottom composer.
2. Pi advances the same diagnosis thread and calls registered system CLI capabilities.
3. The main workspace stays conversation-only.
4. Structured evidence and charts remain in the separate visualization view.

## Local Runtime

- Electron shell owns the desktop window.
- React renderer owns the Codex-style thread UI.
- `preload.cjs` exposes a narrow `window.astock` API.
- `piBridge.cjs` runs one ephemeral Pi agent turn and consumes Pi's JSON event stream incrementally.
- `piExtensions/astockCli.ts` is the only Pi tool. Pi built-in shell and file tools are disabled.
- `factor_research/apps/agent_cli.py` exposes the existing Agent tool registry as a machine-readable CLI and executes only tools registered as `readonly`.
- `readServiceClient.cjs` keeps the local Python API at `http://127.0.0.1:8011` as a conservative fallback when Pi does not return a complete stock profile.

Pi chooses skills and reads capabilities, but its free-form narrative is not financial evidence. The client builds displayed stock conclusions from the CLI payload so unsupported model claims cannot become product output.

## Commands

```bash
npm test
npm run dev
```

Set `ASTOCK_READ_SERVICE_URL` to point at a different local API endpoint.

Pi must have at least one configured model, not only an installed binary:

```bash
pi --offline --list-models
```

Optional runtime overrides:

```bash
ASTOCK_PI_MODEL=deepseek/deepseek-v4-flash
ASTOCK_PI_THINKING=low
ASTOCK_PI_TIMEOUT_MS=60000
```

If dependencies were installed with `--ignore-scripts`, Electron's runtime binary may be missing. Run `npm rebuild electron` once in this directory before launching the desktop window.

## Double-click Launch

Open the app from Finder:

```text
desktop/stock-diagnosis-client/AStock Lens.app
```

The launcher opens a visible Terminal session, starts the fallback Python read service on `127.0.0.1:8011`, then starts the Electron + React client. Runtime logs and pid files are written under `.runtime/` and are ignored by git.

If Electron's macOS runtime binary is missing, the launcher tries `npm rebuild electron` once with `https://npmmirror.com/mirrors/electron/` and a default 180 second timeout. On networks that still block the download, run this one-time repair from `desktop/stock-diagnosis-client/`:

```bash
ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ npm rebuild electron
```

Set `ASTOCK_ELECTRON_REBUILD_TIMEOUT_SECONDS` if the first binary download needs a longer timeout.

If macOS kills Electron with `SIGKILL`, the downloaded `Electron.app` signature is usually damaged. The launcher verifies and repairs this with a local ad-hoc signature. Manual repair:

```bash
codesign --force --deep --sign - node_modules/electron/dist/Electron.app
```
