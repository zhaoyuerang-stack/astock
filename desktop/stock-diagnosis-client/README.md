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
