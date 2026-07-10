# AStock Lens Desktop

Standalone Electron + React client for the personal stock diagnosis product track.

This app intentionally does not reuse the current `web/` information architecture. It keeps the product surface focused on one workflow:

1. User asks about one stock from the bottom composer.
2. The client creates or advances a diagnosis thread.
3. The main workspace shows task steps and a conservative decision card.
4. The right panel shows evidence, limitations, and follow-up prompts.

## Local Runtime

- Electron shell owns the desktop window.
- React renderer owns the Codex-style thread UI.
- `preload.cjs` exposes a narrow `window.astock` API.
- `readServiceClient.cjs` reads the local Python API at `http://127.0.0.1:8011` by default.
- `piBridge.cjs` uses the installed `pi` CLI in ephemeral no-tools mode for optional explanation.

The agent layer may explain and advance diagnosis tasks, but deterministic Python read services remain the source for financial evidence.

## Commands

```bash
npm test
npm run dev
```

Set `ASTOCK_READ_SERVICE_URL` to point at a different local API endpoint.

If dependencies were installed with `--ignore-scripts`, Electron's runtime binary may be missing. Run `npm rebuild electron` once in this directory before launching the desktop window.

## Double-click Launch

Open the app from Finder:

```text
desktop/stock-diagnosis-client/AStock Lens.app
```

The launcher opens a visible Terminal session, starts the local Python read service on `127.0.0.1:8011`, then starts the Electron + React client. Runtime logs and pid files are written under `.runtime/` and are ignored by git.

If Electron's macOS runtime binary is missing, the launcher tries `npm rebuild electron` once with `https://npmmirror.com/mirrors/electron/` and a default 180 second timeout. On networks that still block the download, run this one-time repair from `desktop/stock-diagnosis-client/`:

```bash
ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ npm rebuild electron
```

Set `ASTOCK_ELECTRON_REBUILD_TIMEOUT_SECONDS` if the first binary download needs a longer timeout.

If macOS kills Electron with `SIGKILL`, the downloaded `Electron.app` signature is usually damaged. The launcher verifies and repairs this with a local ad-hoc signature. Manual repair:

```bash
codesign --force --deep --sign - node_modules/electron/dist/Electron.app
```
