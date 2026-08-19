"""Reference scenario (stub): the agent authorization decision operation.

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

# The outcomes under which the action proceeds. Defined once here and used by every
# emitter below, so the scenario has a single statement of it.
PERMITTING = ("allow", "warn", "transform")


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


def _set_decision_attributes(span, decision: Decision) -> None:
    span.set_attribute("gen_ai.operation.name", OP)
    span.set_attribute("gen_ai.agent.authorization.outcome", decision.outcome)
    span.set_attribute("gen_ai.agent.authorization.policy.name", decision.policy)
    span.set_attribute("gen_ai.agent.authorization.policy.version", decision.policy_version)
    span.set_attribute("gen_ai.agent.capability", decision.capability)
    if decision.outcome != "allow" and decision.reason:
        span.set_attribute("gen_ai.agent.authorization.reason", decision.reason)
    for k, v in decision.signals.items():          # optional enrichment
        span.set_attribute(k, v)


def authorize_and_maybe_execute(gate: Gate, capability: str) -> Decision:
    """A deciding component that also creates the span for the permitted action.

    This is the one case the convention's Correlation paragraph covers: the component
    creates that span itself, in the same process and inside this span's context, so it
    lands beneath the decision. It is one conformant shape among several, not the
    required one. `decide_only` and `decide_out_of_process` below are equally conformant.
    """
    with tracer.start_as_current_span(f"{OP} {capability}") as span:
        decision = gate.decide(capability)
        _set_decision_attributes(span, decision)

        if decision.outcome in PERMITTING:
            with tracer.start_as_current_span("execute_tool database.read"):
                pass  # the permitted action runs here, beneath the decision that permitted it
        # deny / escalate / error: no child execute span
        return decision


def decide_only(gate: Gate, capability: str) -> Decision:
    """A deciding component that emits its decision and nothing else.

    This is what both public producers actually do. AIM emits `fga.authorize` with FGA
    step children and no execute span anywhere; AGT's merged telemetry emits metrics and
    registers no tracer. The action runs, but it is executed and instrumented elsewhere,
    so no span for it appears under the decision. This shape is CONFORMANT.
    """
    with tracer.start_as_current_span(f"{OP} {capability}") as span:
        decision = gate.decide(capability)
        _set_decision_attributes(span, decision)
        return decision


def decide_out_of_process(gate: Gate, capability: str) -> Decision:
    """A gateway that decides in one service and forwards to another.

    The executor creates its own span from the propagated context. Stock propagation
    injects the context current at the forward point, so the execute span lands as a
    SIBLING of the decision span under a common parent. This shape is CONFORMANT: the
    parent-child relation is not available to either party.
    """
    with tracer.start_as_current_span(f"gateway {capability}"):
        with tracer.start_as_current_span(f"{OP} {capability}") as span:
            decision = gate.decide(capability)
            _set_decision_attributes(span, decision)
        if decision.outcome in PERMITTING:
            with tracer.start_as_current_span("execute_tool database.read"):
                pass  # executed downstream, under the gateway span, not the decision
        return decision


def evaluate_after_the_fact(gate: Gate, capability: str) -> Decision:
    """The NON-INTERPOSED shape, which this operation does NOT model.

    The action runs and completes first; a policy is evaluated over it afterwards, from
    activity reported to the evaluating component rather than routed through it. No
    answer it reaches could have prevented the action, so the decision span is a SIBLING
    of the execute span and never its parent.

    The convention says instrumentation SHOULD NOT emit this operation for such an
    evaluation. Nothing in the emitted data marks it, which is exactly why the rule is a
    producer duty and not a property a consumer can check: this shape is byte-identical
    to a conformant out-of-process decision. The validator records that rather than
    pretending to detect it.
    """
    with tracer.start_as_current_span("execute_tool database.read"):
        pass  # the action runs, conditioned on nothing
    with tracer.start_as_current_span(f"{OP} {capability}") as span:
        decision = gate.decide(capability)
        _set_decision_attributes(span, decision)
        return decision


if __name__ == "__main__":
    authorize_and_maybe_execute(Gate(), "database.read")
