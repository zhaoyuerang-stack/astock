# MODULE_STATUS

Status: CLI_ENTRYPOINTS

Role: Human-operated command-line entrypoints for factory, portfolio, stock diagnostics, and contribution views.

Keep because: these files are executable tools, so low import inbound count does not imply dead code.

Boundary:
- CLI orchestration only.
- Core logic should live in `services/`, `workflow/`, `factory/`, `portfolio/`, or `strategies/`.
- Do not make production runtime depend on CLI modules.
