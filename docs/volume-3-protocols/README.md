# Volume 3 — Protocol Specifications

Every interface in the system, defined explicitly. These are the internal
standards: modules and capabilities communicate **only** through these
interfaces (Invariant I4). Each protocol is versioned; breaking changes bump
the major version and require an ADR.

Canonical machine-readable schemas live in `nexus/schemas/`. On conflict,
this volume wins and the code must be fixed.

| Protocol | File | Status |
|----------|------|--------|
| Event Bus | [event-bus.md](event-bus.md) | v1, implemented |
| Task API | [task-api.md](task-api.md) | v1, implemented (kernel scope) |
| Session API | [session-api.md](session-api.md) | v1, implemented |
| Capability Manifest | [capability-manifest.md](capability-manifest.md) | v1, schema implemented |
| Memory API | [memory-api.md](memory-api.md) | v1, spec |
| Plugin API | [plugin-api.md](plugin-api.md) | draft |

External protocols (MCP, A2A, REST/WebSocket/gRPC, Git, SSH) are absorbed as
*adapters at the capability layer*: an adapter translates the external protocol
into these internal interfaces. The kernel never speaks an external protocol
directly.
