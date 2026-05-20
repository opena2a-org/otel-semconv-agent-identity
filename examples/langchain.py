"""LangChain to OpenTelemetry bridge emitting OpenA2A agent identity semantic conventions.

This file is part of the proposal at https://github.com/opena2a-org/otel-semconv-agent-identity.

Add ten lines to your existing LangChain agent setup to emit agent.id, agent.capability,
and FGA outcome attributes on OpenTelemetry spans. See examples/README.md for usage.

Apache 2.0 licensed.
"""

# Copyright 2026 OpenA2A Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from opentelemetry import trace
    from opentelemetry.trace import Span, Status, StatusCode, Tracer

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OTEL_AVAILABLE = False
    trace = None  # type: ignore[assignment]
    Span = Any  # type: ignore[assignment,misc]
    Status = Any  # type: ignore[assignment,misc]
    StatusCode = Any  # type: ignore[assignment,misc]
    Tracer = Any  # type: ignore[assignment,misc]

try:
    from langchain_core.callbacks import BaseCallbackHandler

    _LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LANGCHAIN_AVAILABLE = False

    class BaseCallbackHandler:  # type: ignore[no-redef]
        """Stub used only when langchain_core is not installed.

        The real BaseCallbackHandler is imported when LangChain is available. This stub
        exists so the module can be imported and inspected without LangChain installed,
        which is helpful for documentation and testing tooling.
        """


# Locked attribute names. Do not rename without updating the proposal at
# https://github.com/opena2a-org/otel-semconv-agent-identity/blob/main/registry/agent.yaml
# and the AIM backend at apps/backend/docs/OBSERVABILITY.md.
ATTR_AGENT_ID = "agent.id"
ATTR_AGENT_PUBKEY_ALG = "agent.public_key.algorithm"
ATTR_AGENT_CAPABILITY = "agent.capability"
ATTR_AGENT_TRUST_SCORE = "agent.trust_score"
ATTR_AGENT_DRIFT_SCORE = "agent.drift_score"
ATTR_AGENT_SCAN_VERDICT = "agent.scan_verdict"
ATTR_FGA_STEP = "fga.step"
ATTR_FGA_OUTCOME = "fga.outcome"
ATTR_FGA_DENIED_BY = "fga.denied_by"

_SPAN_NAME = "agent.action.invoke"
_DEFAULT_TRACER_NAME = "opena2a.langchain"


class AgentIdentityCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler emitting OpenA2A agent identity attributes on OTel spans.

    Wrap a LangChain AgentExecutor with this handler to emit the nine attributes defined
    in the SemConv proposal for each agent action. The handler creates an OpenTelemetry
    span on agent_action and ends it on tool_end, tool_error, or agent_finish.

    Parameters
    ----------
    agent_id:
        Stable identifier for the agent instance. Required. Emitted as agent.id.
    public_key_algorithm:
        Cryptographic algorithm of the agent's identity keypair. Default "ed25519".
    trust_score:
        Producer-emitted trust score at decision time. Range 0.0 to 1.0. Default 1.0.
    drift_score:
        Producer-emitted behavioral drift score at decision time. Range 0.0 to 1.0. Default 0.0.
    scan_verdict:
        Most recent security scan verdict. Default "unknown".
    tracer:
        Optional OpenTelemetry Tracer. If None, one is obtained via
        trace.get_tracer("opena2a.langchain").
    """

    def __init__(
        self,
        agent_id: str,
        public_key_algorithm: str = "ed25519",
        trust_score: float = 1.0,
        drift_score: float = 0.0,
        scan_verdict: str = "unknown",
        tracer: Optional[Tracer] = None,
    ) -> None:
        if not _OTEL_AVAILABLE:
            raise ImportError(
                "opentelemetry packages are not installed. Install with: "
                "pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp"
            )
        if not _LANGCHAIN_AVAILABLE:
            raise ImportError(
                "langchain_core is not installed. Install with: "
                "pip install langchain opentelemetry-api opentelemetry-sdk "
                "opentelemetry-exporter-otlp"
            )
        super().__init__()
        self.agent_id = agent_id
        self.public_key_algorithm = public_key_algorithm
        self.trust_score = float(trust_score)
        self.drift_score = float(drift_score)
        self.scan_verdict = scan_verdict
        self._tracer: Tracer = tracer or trace.get_tracer(_DEFAULT_TRACER_NAME)
        self._spans: Dict[Any, Span] = {}

    def _base_attributes(self, capability: str) -> Dict[str, Any]:
        return {
            ATTR_AGENT_ID: self.agent_id,
            ATTR_AGENT_PUBKEY_ALG: self.public_key_algorithm,
            ATTR_AGENT_CAPABILITY: capability,
            ATTR_AGENT_TRUST_SCORE: self.trust_score,
            ATTR_AGENT_DRIFT_SCORE: self.drift_score,
            ATTR_AGENT_SCAN_VERDICT: self.scan_verdict,
            ATTR_FGA_STEP: "capability_check",
        }

    def on_agent_action(self, action: Any, **kwargs: Any) -> None:
        """Start a span for the agent action. Stores it by run_id for later end events."""
        run_id = kwargs.get("run_id")
        capability = getattr(action, "tool", "unknown")
        span = self._tracer.start_span(_SPAN_NAME)
        for key, value in self._base_attributes(capability).items():
            span.set_attribute(key, value)
        self._spans[run_id] = span

    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        """No-op when a span is already active for the parent agent action."""
        return None

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        """Mark the active span as ALLOW and end it."""
        run_id = kwargs.get("run_id")
        span = self._spans.pop(run_id, None)
        if span is None:
            return
        span.set_attribute(ATTR_FGA_OUTCOME, "ALLOW")
        span.set_status(Status(StatusCode.OK))
        span.end()

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        """Mark the active span as ERROR with denied_by=tool_error and end it."""
        run_id = kwargs.get("run_id")
        span = self._spans.pop(run_id, None)
        if span is None:
            return
        span.set_attribute(ATTR_FGA_OUTCOME, "ERROR")
        span.set_attribute(ATTR_FGA_DENIED_BY, "tool_error")
        span.record_exception(error)
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.end()

    def on_agent_finish(self, finish: Any, **kwargs: Any) -> None:
        """End any still-open span with ALLOW if not already ended."""
        run_id = kwargs.get("run_id")
        span = self._spans.pop(run_id, None)
        if span is None:
            return
        span.set_attribute(ATTR_FGA_OUTCOME, "ALLOW")
        span.end()


def _setup_otel_for_demo() -> bool:
    """Wire a TracerProvider with an OTLP exporter at localhost:4317. Returns success."""
    try:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    except ImportError as exc:
        print(
            "Missing OpenTelemetry SDK or OTLP exporter. Install with:\n"
            "  pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp\n"
            f"Underlying error: {exc}"
        )
        return False

    provider = TracerProvider()
    exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return True


def _demo() -> None:
    """Run a minimal example. Print the trace_id so the user can find the trace in Tempo.

    If LangChain is not installed the function prints a clear install hint and returns.
    If OTel SDK or the OTLP exporter is missing the function prints a clear install hint and
    returns. If a local OTLP collector is not running the span is still created locally; the
    BatchSpanProcessor logs an export failure when it tries to flush.
    """
    if not _OTEL_AVAILABLE:
        print(
            "OpenTelemetry packages are not installed in this environment. To run this demo:\n"
            "  pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp\n"
            "Then also install LangChain:\n"
            "  pip install langchain\n"
        )
        return

    if not _LANGCHAIN_AVAILABLE:
        print(
            "LangChain is not installed in this environment. To run this demo:\n"
            "  pip install langchain opentelemetry-api opentelemetry-sdk "
            "opentelemetry-exporter-otlp\n"
        )
        return

    if not _setup_otel_for_demo():
        return

    try:
        from langchain_core.agents import AgentAction
    except ImportError:
        print(
            "langchain_core is installed but AgentAction could not be imported. "
            "The bridge class is still functional. Skipping the live demo."
        )
        return

    from uuid import uuid4

    tracer = trace.get_tracer(f"{_DEFAULT_TRACER_NAME}.demo")
    with tracer.start_as_current_span("demo.root") as root_span:
        handler = AgentIdentityCallbackHandler(agent_id="demo-agent-001", tracer=tracer)
        run_id = uuid4()
        action = AgentAction(tool="database.read", tool_input="select 1", log="demo")
        handler.on_agent_action(action, run_id=run_id)
        handler.on_tool_end("ok", run_id=run_id)
        ctx = root_span.get_span_context()
        trace_id_hex = format(ctx.trace_id, "032x")
        print(f"Demo span emitted. Trace ID hex: {trace_id_hex}")
        print(
            "If a local Tempo is running at localhost:4317, the span should land there "
            "within a few seconds. Open Grafana at http://localhost:3001 and search for "
            "this trace ID."
        )


if __name__ == "__main__":
    _demo()
