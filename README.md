# OpenTelemetry SemConv for Agent Identity

OpenTelemetry semantic conventions for AI agent authorization observability. Reference implementation for the proposal filed at https://github.com/open-telemetry/semantic-conventions-genai/issues/180.

## What this is

A focused proposal capturing agent authorization decisions in OpenTelemetry traces, metrics, and logs. The attributes are scoped under the `gen_ai.agent.*` namespace per the OpenTelemetry GenAI semantic conventions; the proposal is filed upstream as [open-telemetry/semantic-conventions-genai#291](https://github.com/open-telemetry/semantic-conventions-genai/pull/291) (issue [#180](https://github.com/open-telemetry/semantic-conventions-genai/issues/180)). The OpenA2A Agent Identity Management (AIM) backend is the reference producer; see the Reference implementation section for its current emission status.

## The attributes

Core identity:
- `gen_ai.agent.id`
- `gen_ai.agent.public_key.algorithm` (fail-closed verifier guidance on unknown algorithm identifiers)

Action context:
- `gen_ai.agent.capability`

Decision inputs (producer-emitted), each paired with an opaque method/version token:
- `gen_ai.agent.trust.score` / `gen_ai.agent.trust.method`
- `gen_ai.agent.drift.score` / `gen_ai.agent.drift.method`
- `gen_ai.agent.scan.verdict` / `gen_ai.agent.scan.method`

FGA decision path (namespace placement pending the working-group decision in #180; deferred from #291):
- `fga.step`
- `fga.outcome`
- `fga.denied_by`

See `registry/agent.yaml` and `registry/fga.yaml` for full definitions.

## Framing

The `trust.score`, `drift.score`, and `scan.verdict` attributes are producer-emitted decision inputs, not normative computed values. The producer computes the score (or selects the verdict) using whatever method makes sense for their domain. The convention only standardizes the attribute name, type, and range (or value set) so downstream observers can correlate. Each is paired with a `.method` token — an opaque, producer-scoped string for the method and version that produced the value, compared for equality only — so a consumer can distinguish a change in the scoring method from a real change in the agent's behaviour. Producers documenting their scoring or scanning methodology is recommended but not normative.

For `scan.verdict` specifically: in the OpenA2A reference implementation, the value is read from a per-agent `agent_security_contexts` record that is intended to be written by an integration with the HackMyAgent scanner via the Registry's `PATCH /internal/asc/:agentId` endpoint. That producer integration is on the roadmap; the demo seeds a `'CLEAN'` value into the same record so the attribute appears on the trace end-to-end. Other producers can wire any scanner they trust to the same convention.

## Reference implementation

The AIM backend at https://github.com/opena2a-org/agent-identity-management computes the producer-side signals today in `apps/backend/internal/application/fga_engine.go` — identity, capability, trust and drift scores, and the FGA decision path are emitted live; the scan verdict is read from a producer-populated `agent_security_contexts` record (see the Framing section for the scanner integration status).

Note on naming: the live AIM emitter currently uses the pre-scoping attribute names (`agent.trust_score`, `agent.drift_score`, `agent.scan_verdict`, etc.) documented in `docs/REFERENCE-IMPLEMENTATION.md`. The proposal in this repo and upstream #291 scopes them under `gen_ai.agent.*`, splits the scores into `.score`/`.method` pairs, and adds the `.method` tokens. AIM's migration to the scoped names is tracked and lands with the emitter update; until then the proposal is intentionally ahead of the reference emitter.

A LangChain instrumentation example is at `examples/langchain.py`.

## Try it

Run the AIM backend OTel demo stack at `apps/backend/deployments/otel-demo` and observe FGA authorization spans in Grafana Tempo with these 9 attributes attached.

## Standards process

This proposal is tracked at https://github.com/open-telemetry/semantic-conventions-genai/issues/180. Comments and review welcome there.

## Contributing

See `CONTRIBUTING.md`.

## License

Apache 2.0.
