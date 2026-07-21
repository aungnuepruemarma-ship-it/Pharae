# Protocol — Capability Manifest (v1)

Schema: `nexus/schemas/capability.py`. Consumed by the Registry (Stage 2) and
Router (Stage 3). This is the contract that keeps the kernel provider-agnostic
(Invariant I1): the runtime reasons over these fields and nothing else.

## Manifest

```
CapabilityManifest {
  # Identity
  name: str                  # unique, e.g. "browser.playwright"
  capability_type: str       # what it IS: "browser", "code", "research", "model", ...
  version: str               # semver
  description: str

  # Contract
  input_schema: dict         # JSON-schema-shaped description of accepted input
  output_schema: dict        # ... of produced output
  permissions: [str]         # e.g. "net.fetch", "fs.write", "proc.spawn"
  constraints: dict          # rate limits, max payload, environment needs

  # Routing signals
  cost: float                # normalized cost per invocation (0 = free)
  latency_ms: float          # expected latency
  reliability: float         # [0,1] — observed success rate
  trust_score: float         # [0,1] — earned via verified history
  evidence_score: float      # [0,1] — how verifiable its outputs are
  confidence: float          # [0,1] — self-assessed fit, capped by trust
  strengths: [str]           # free-form tags for routing context
}
```

## Rules

- `capability_type` is drawn from an open but registered vocabulary; new types
  are added by spec update here, not ad hoc.
- `reliability` and `trust_score` are **owned by the learning pipeline** after
  registration: a capability declares initial estimates, and only verified run
  history may move them (Invariant I2).
- `permissions` are enforced by the security layer at execution time; a
  capability invoking beyond its declared permissions is a policy violation
  that fails the task.
- Manifests are validated at registration; malformed or overpermissioned
  manifests are rejected with reasons.
- Two capabilities never depend on each other's manifests; composition happens
  in plans (Invariant I4).
