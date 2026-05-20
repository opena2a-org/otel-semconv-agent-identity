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

The `trust_score` and `drift_score` attributes are producer-emitted decision inputs, not normative computed values. The producer computes the score using whatever method makes sense for their domain. The convention only standardizes the attribute name, type, and range so downstream observers can correlate. Producers documenting their scoring methodology is recommended but not normative.

## Reference implementation

The AIM backend at https://github.com/opena2a-org/agent-identity-management emits all 9 attributes today at `apps/backend/internal/application/fga_engine.go`.

A LangChain instrumentation example is at `examples/langchain.py`.

## Try it

Run the AIM backend OTel demo stack at `apps/backend/deployments/otel-demo` and observe FGA authorization spans in Grafana Tempo with these 9 attributes attached.

## Standards process

This proposal is tracked at https://github.com/open-telemetry/semantic-conventions-genai/issues/180. Comments and review welcome there.

## Contributing

See `CONTRIBUTING.md`.

## License

Apache 2.0.
