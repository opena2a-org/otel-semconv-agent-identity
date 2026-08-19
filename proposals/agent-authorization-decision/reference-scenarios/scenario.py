"""Reference scenario (stub) — the agent authorization decision operation.

Models the deciding component (a PDP / gate) as a `decide()` that returns a decision
object, and sets the `gen_ai.execute_authorization` span attributes FROM that returned
decision rather than from literals. Mirrors the shape of AIM's FGAEngine.Authorize()
and the #291 `reference/scenarios/agent-authorization` scenario.

STUB: not yet wired to the SemConv Weaver live-check. See README.md TODO.
"""
from dataclasses import dataclass, field
from typing import Optional

from opentelemetry import trace

tracer = trace.get_tracer("agent-authorization-scenario")

OP = "execute_authorization"


@dataclass
class Decision:
    """What a gate's decide() returns. The span is populated from this object."""
    outcome: str                      # allow | deny | warn | escalate | transform | error
    policy: str                       # opaque policy/ruleset id (name only, no revision)
    policy_version: str               # revision in force at evaluation time
    capability: str                   # what was being authorized
    reason: Optional[str] = None      # required when outcome != allow
    # optional producer-specific signal enrichment (only if the gate computes them)
    signals: dict = field(default_factory=dict)


class Gate:
    """Minimal PDP. Real producers (AIM's FGA engine, AGT's acs_* gate) do the work;
    here we return a fixed decision so the scenario is deterministic."""

    def decide(self, capability: str) -> Decision:
        return Decision(
            outcome="deny",
            policy="aim/fga",
            policy_version="2026.08.1",
            capability=capability,
            reason="capability_denied",
            signals={
                "gen_ai.agent.trust.score": 0.42,
                "gen_ai.agent.trust.method": "aim/trust-calculator",
                "gen_ai.agent.scan.verdict": "findings",
                "gen_ai.agent.scan.method": "aim/registry-asc",
            },
        )


def authorize_and_maybe_execute(gate: Gate, capability: str) -> Decision:
    """Emit exactly one decision span, set from the returned decision object.

    Invariant: a child execute span is emitted IFF the decision permitted execution.
    A `deny` leaves a present decision span with NO child execute span beneath it.
    """
    with tracer.start_as_current_span(f"{OP} {capability}") as span:
        decision = gate.decide(capability)
        span.set_attribute("gen_ai.operation.name", OP)
        span.set_attribute("gen_ai.agent.authorization.outcome", decision.outcome)
        span.set_attribute("gen_ai.agent.authorization.policy.name", decision.policy)
        span.set_attribute("gen_ai.agent.authorization.policy.version", decision.policy_version)
        span.set_attribute("gen_ai.agent.capability", decision.capability)
        if decision.outcome != "allow" and decision.reason:
            span.set_attribute("gen_ai.agent.authorization.reason", decision.reason)
        for k, v in decision.signals.items():          # optional enrichment
            span.set_attribute(k, v)

        if decision.outcome in ("allow", "warn", "transform"):
            with tracer.start_as_current_span("execute_tool database.read"):
                pass  # the permitted action runs here
        # deny / escalate / error: no child execute span (invariant 3)
        return decision


if __name__ == "__main__":
    authorize_and_maybe_execute(Gate(), "database.read")
