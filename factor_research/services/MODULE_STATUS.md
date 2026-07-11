# MODULE_STATUS

Status: ONLINE

Role: Product-facing service layer, split into read models, actions, and agent support.

Keep because: it is the controlled boundary between API/Web and engine/research/runtime internals.

Boundary:
- `services/read`: query views and artifact reads through approved repositories.
- `services/actions`: controlled execution or workflow actions.
- `services/agent`: LLM/tool support, never alpha validity authority.
- API should call services rather than lower layers directly.
