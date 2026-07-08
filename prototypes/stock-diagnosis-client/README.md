# AStock Lens Desktop Client Prototype

This is the first standalone prototype for a Codex-style personal stock diagnosis client.

Open `index.html` directly in a browser. It does not depend on the existing `web/` app, a dev server, or external packages.

## Product Boundary

- Left panel: stock diagnosis threads, not module navigation.
- Middle panel: current diagnosis task, conservative decision card, and task timeline.
- Bottom composer: primary input fixed at the bottom of the middle panel.
- Right panel: evidence, limits, and follow-up prompts.

The prototype is read-only and does not issue trade commands. Future Electron and Pi integration should keep the same boundary: the agent may create and advance diagnosis tasks, but final financial evidence must come from deterministic local read services.

## Checks

Run:

```bash
node prototypes/stock-diagnosis-client/test_contract.mjs
```
