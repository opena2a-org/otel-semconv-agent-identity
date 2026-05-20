# Copyright 2026 OpenA2A Inc.
# Licensed under the Apache License, Version 2.0.
# See LICENSE at the repository root.

"""Minimal LangChain agent. Reference implementation for the Observability Summit
talk on 2026-05-22.

Demonstrates the 10-line instrumentation pattern that emits the 9 locked SemConv
attributes proposed at https://github.com/open-telemetry/semantic-conventions-genai/issues/180.

Run: python examples/minimal_langchain_agent.py
"""

import importlib.util
import os
import sys
from uuid import uuid4

try:
    from langchain_core.agents import AgentAction
    from langchain_core.tools import tool
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except ImportError as exc:
    print(f"Required package not installed: {exc.name}. Install with:")
    print("  pip install langchain opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp")
    sys.exit(0)

# Import AgentIdentityCallbackHandler from sibling langchain.py without shadowing
# the third-party langchain package on sys.path.
_BRIDGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "langchain.py")
_spec = importlib.util.spec_from_file_location("opena2a_bridge", _BRIDGE_PATH)
_bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bridge)
AgentIdentityCallbackHandler = _bridge.AgentIdentityCallbackHandler


@tool
def fake_tool(query: str) -> str:
    """No-op tool that returns a hardcoded greeting."""
    return "hello, world"

# Ten-line instrumentation. In a real app, attach the handler via
# AgentExecutor(agent=..., tools=[fake_tool], callbacks=[handler]).invoke({...}).
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="localhost:4317", insecure=True))
)
handler = AgentIdentityCallbackHandler(agent_id="minimal-demo-001")

if __name__ == "__main__":
    tracer = trace.get_tracer("opena2a.langchain.minimal")
    with tracer.start_as_current_span("demo.root") as root:
        run_id = uuid4()
        handler.on_agent_action(AgentAction(tool="fake_tool", tool_input="hi", log="demo"), run_id=run_id)
        handler.on_tool_end(fake_tool.invoke("hi"), run_id=run_id)
        trace_id_hex = format(root.get_span_context().trace_id, "032x")
        print(f"Trace ID: {trace_id_hex}")
