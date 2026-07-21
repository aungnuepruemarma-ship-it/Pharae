# Research Agenda

Open questions the architecture deliberately leaves open, with the evidence
that would settle each. Findings land in `experiments/`; conclusions graduate
via ADR.

## Open Questions

1. **Capability routing algorithms.** When does benchmark-driven routing beat
   ordered rules? Needs: ≥N recorded `RoutingDecision`s with verified outcomes
   (Stage 3 produces the data).
2. **Memory promotion strategies.** What evidence threshold and repetition
   count should gate working → episodic → semantic/procedural promotion?
   Needs: promotion pipeline (Stage 5–6) plus regression benchmarks.
3. **Trust calibration.** How fast should `trust_score` move on success/
   failure, and should decay apply to idle capabilities?
4. **Human-AI collaboration.** Which task classes should *require* approval
   regardless of confidence (progressive autonomy schedule)?
5. **Autonomous experimentation.** Can the runtime safely design and run its
   own benchmark experiments inside the sandbox boundary?

## Future Directions (post-Phase 3)

- Multi-runtime federation
- Distributed capability networks / capability exchange
- Formal verification of planner and promotion-gate properties
- Adaptive scheduling
- Scientific discovery workflows (hypothesis → experiment → conclusion as a
  first-class plan shape)

## Standing comparisons to maintain

Agent runtimes, OS design, distributed systems, workflow engines, knowledge
graphs, scheduling algorithms, human memory models, continuous learning — one
living literature-review doc each, with explicit "what Pharae takes from this"
sections.
