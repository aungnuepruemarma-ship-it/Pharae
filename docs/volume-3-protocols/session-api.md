# Protocol — Session API (v1)

Implemented: `nexus/kernel/sessions.py`.

## Session

```
Session {
  id: str            # "ses-<hex>"
  status: ACTIVE | ENDED
  created_at, ended_at?
  metadata: dict
}
```

## Operations

- `create(metadata?) → Session` — allocates the session, creates its isolated
  state namespace `session:<id>`, emits `session.started`.
- `get(id) → Session | None`
- `active() → [Session]`
- `end(id)` — idempotent; marks `ENDED`, clears the session namespace, emits
  `session.ended`.

## Rules

- Each session's state lives only in its own namespace; sessions never read or
  write each other's namespaces.
- The session id is the correlation id for session-scoped events: kernel
  components stamp `session_id` into event payloads where applicable.
- Runs reference exactly one session (`Run.session_id`); a session may host
  many runs over its lifetime.
- Ending a session does not delete durable outputs (runs, evidence, artifacts);
  it releases only ephemeral working state.
