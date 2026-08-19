"""Reference implementation for the agent authorization *decision* operation.

Models the deciding component (a policy decision point / gate) as an
``AuthorizationGate`` whose ``decide`` call returns one ``AuthorizationDecision``.
The instrumentation emits one ``gen_ai.execute_authorization`` span per decision and
sets the span attributes from the returned decision object, not from literals -- so both
the instrumentation point (the gate) and the data source (the decision) are visible.

Two decisions are exercised to demonstrate the structural invariants:

  * an ``allow`` decision, under which a child ``execute_tool`` span runs (invariant 2:
    a child execute span is present iff the decision permitted execution);
  * a ``deny`` decision, which is a present span with NO child execute span beneath it
    (invariant 3: a denial stays auditable; "never attempted" would be no span at all).

The optional ``gen_ai.agent.{trust,drift,scan}.*`` and ``public_key.algorithm`` signals
are producer-specific enrichment on the decision span (a producer such as AIM computes
them; a metrics-only producer such as AGT does not).
"""

from dataclasses import dataclass, field

from reference_shared import (
    flush_and_shutdown,
    reference_tracer,
    setup_otel,
)

_reference_tracer = reference_tracer()


@dataclass(frozen=True)
class AuthorizationDecision:
    """What the deciding component returns for one agent action."""

    outcome: str            # allow | deny | warn | escalate | transform | error
    policy: str
    capability: str
    reason: str | None = None                 # required when outcome != allow
    policy_version: str = "2026.08.1"
    signals: dict = field(default_factory=dict)  # optional producer enrichment


class AuthorizationGate:
    """Minimal stand-in for the PDP. Returns fixed decisions so the scenario stays
    deterministic; the point it demonstrates is structural -- attributes are read from
    the returned decision, not bound at the instrumentation site."""

    def decide(self, *, capability: str, allow: bool) -> AuthorizationDecision:
        if allow:
            return AuthorizationDecision(
                outcome="allow",
                policy="aim/fga",
                capability=capability,
                signals={
                    "gen_ai.agent.public_key.algorithm": "Ed25519",
                    "gen_ai.agent.public_key.verification": "verified",
                    "gen_ai.agent.trust.score": 0.93,
                    "gen_ai.agent.trust.method": "trust-model@2.3.1",
                    "gen_ai.agent.drift.score": 0.04,
                    "gen_ai.agent.drift.method": "embedding-cosine@1.4",
                    "gen_ai.agent.scan.verdict": "clean",
                    "gen_ai.agent.scan.method": "scanner@1.2.0",
                },
            )
        return AuthorizationDecision(
            outcome="deny",
            policy="aim/fga",
            capability=capability,
            reason="capability_denied",
            signals={
                "gen_ai.agent.trust.score": 0.41,
                "gen_ai.agent.trust.method": "trust-model@2.3.1",
                "gen_ai.agent.scan.verdict": "findings",
                "gen_ai.agent.scan.method": "scanner@1.2.0",
            },
        )


def _emit_decision(decision: AuthorizationDecision):
    """Emit one execute_authorization span, set from the returned decision object."""
    span_attributes = {
        "gen_ai.operation.name": "execute_authorization",
        "gen_ai.agent.authorization.outcome": decision.outcome,
        "gen_ai.agent.authorization.policy.name": decision.policy,
        "gen_ai.agent.authorization.policy.version": decision.policy_version,
        "gen_ai.agent.capability": decision.capability,
    }
    if decision.outcome != "allow" and decision.reason is not None:
        span_attributes["gen_ai.agent.authorization.reason"] = decision.reason
    span_attributes.update(decision.signals)

    with _reference_tracer.start_as_current_span(
        f"execute_authorization {decision.capability}", attributes=span_attributes
    ):
        # Invariant 2/3: a child execute span is emitted iff execution was permitted.
        if decision.outcome in ("allow", "warn", "transform"):
            with _reference_tracer.start_as_current_span(
                "execute_tool query_database",
                attributes={
                    "gen_ai.operation.name": "execute_tool",
                    "gen_ai.tool.name": "query_database",
                    "gen_ai.tool.call.id": "call_ref_0001",
                    "gen_ai.tool.type": "function",
                },
            ):
                pass


def run_agent_authorization_decision_reference(gate):
    print("  [execute_authorization] allow decision -> child execute_tool span")
    _emit_decision(gate.decide(capability="database.read", allow=True))
    print("  [execute_authorization] deny decision  -> no child execute span")
    _emit_decision(gate.decide(capability="payments.transfer", allow=False))


def main():
    print("=== Reference Implementation: Agent Authorization Decision Operation ===")
    tp, lp, mp = setup_otel()
    run_agent_authorization_decision_reference(AuthorizationGate())
    flush_and_shutdown(tp, lp, mp)


if __name__ == "__main__":
    main()
