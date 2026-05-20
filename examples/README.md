# LangChain to OTel bridge

This example shows how to instrument a LangChain agent to emit OpenA2A agent identity semantic conventions on OpenTelemetry spans.

## What you get

When you wrap your LangChain agent with this callback handler, every agent action produces an OpenTelemetry span with these attributes:

- `agent.id`
- `agent.public_key.algorithm`
- `agent.capability` (set to the invoked tool name)
- `agent.trust_score`
- `agent.drift_score`
- `agent.scan_verdict`
- `fga.step` (set to `"capability_check"`)
- `fga.outcome` (set to `"ALLOW"` on success or `"ERROR"` on tool error)
- `fga.denied_by` (set when `fga.outcome` is `"ERROR"`)

## Install

```
pip install langchain opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
```

## Use

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from langchain.agents import AgentExecutor
from examples.langchain import AgentIdentityCallbackHandler

# Standard OTel setup
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="localhost:4317", insecure=True))
)

# Attach the callback to your agent
handler = AgentIdentityCallbackHandler(agent_id="my-agent-001")
agent_executor = AgentExecutor(agent=your_agent, tools=your_tools, callbacks=[handler])

# Run it
result = agent_executor.invoke({"input": "your prompt"})
```

That is the 10 lines. The handler does the rest.

## See your traces

If you are running the AIM OTel demo stack (`apps/backend/deployments/otel-demo` in `agent-identity-management`), open Grafana at http://localhost:3001 and find your trace in Tempo. The 9 attributes will be on the span.

## Minimal LangChain agent (reference implementation)

`minimal_langchain_agent.py` is a single self-contained file that demonstrates the 10-line instrumentation pattern for the Observability Summit talk. It uses a fake tool that returns a hardcoded string so it runs without any LLM or external API call.

The 10-line instrumentation pattern at the heart of the file:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from langchain.agents import AgentExecutor
from examples.langchain import AgentIdentityCallbackHandler

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="localhost:4317", insecure=True))
)
handler = AgentIdentityCallbackHandler(agent_id="minimal-demo-001")
AgentExecutor(agent=your_agent, tools=your_tools, callbacks=[handler]).invoke({"input": "..."})
```

When the agent runs, the resulting span carries all 9 locked SemConv attributes:

- `agent.id`
- `agent.public_key.algorithm`
- `agent.capability`
- `agent.trust_score`
- `agent.drift_score`
- `agent.scan_verdict`
- `fga.step`
- `fga.outcome`
- `fga.denied_by`

Run it with:

```
python examples/minimal_langchain_agent.py
```

If no Tempo or OpenTelemetry collector is running locally, the spans are still created. The `BatchSpanProcessor` logs an export error in the background and the script exits cleanly.

## License

Apache 2.0.
