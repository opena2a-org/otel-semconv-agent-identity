# OpenTelemetry SemConv for Agent Identity

OpenTelemetry semantic conventions for AI agent authorization observability. Reference implementation for the proposal filed at https://github.com/open-telemetry/semantic-conventions-genai/issues/180.

## What this is

A focused proposal of 9 attributes that capture agent authorization decisions in OpenTelemetry traces, metrics, and logs. The attributes are emitted today by the OpenA2A Agent Identity Management (AIM) backend and are documented as the locked specification at https://github.com/opena2a-org/agent-identity-management `apps/backend/docs/OBSERVABILITY.md`.

## The 9 attributes

Core identity:
- `agent.id`
- `agent.public_key.algorithm`

Action context:
- `agent.capability`

Decision inputs (producer-emitted):
- `agent.trust_score`
- `agent.drift_score`
- `agent.scan_verdict`

FGA decision path:
- `fga.step`
- `fga.outcome`
- `fga.denied_by`

See `registry/agent.yaml` and `registry/fga.yaml` for full definitions.

## Framing

The `trust_score`, `drift_score`, and `scan_verdict` attributes are producer-emitted decision inputs, not normative computed values. The producer computes the score (or selects the verdict) using whatever method makes sense for their domain. The convention only standardizes the attribute name, type, and range (or enum) so downstream observers can correlate. Producers documenting their scoring or scanning methodology is recommended but not normative.

For `scan_verdict` specifically: in the OpenA2A reference implementation, the value is read from a per-agent `agent_security_contexts` record that is intended to be written by an integration with the HackMyAgent scanner via the Registry's `PATCH /internal/asc/:agentId` endpoint. That producer integration is on the roadmap; the demo seeds a `'CLEAN'` value into the same record so the attribute appears on the trace end-to-end. Other producers can wire any scanner they trust to the same convention.

## Reference implementation

The AIM backend at https://github.com/opena2a-org/agent-identity-management emits all 9 attributes today from `apps/backend/internal/application/fga_engine.go`. Eight attributes (`agent.id`, `agent.public_key.algorithm`, `agent.capability`, `agent.trust_score`, `agent.drift_score`, `fga.step`, `fga.outcome`, `fga.denied_by`) are computed live in the FGA decision path. The ninth, `agent.scan_verdict`, is read from a producer-populated `agent_security_contexts` record. See the Framing section above for the current status of the scanner integration that writes to it.

A LangChain instrumentation example is at `examples/langchain.py`.

## Try it

Run the AIM backend OTel demo stack at `apps/backend/deployments/otel-demo` and observe FGA authorization spans in Grafana Tempo with these 9 attributes attached.

## Standards process

This proposal is tracked at https://github.com/open-telemetry/semantic-conventions-genai/issues/180. Comments and review welcome there.

## Contributing

See `CONTRIBUTING.md`.

## License

Apache 2.0.
