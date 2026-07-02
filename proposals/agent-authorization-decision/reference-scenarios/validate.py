"""Validate the decision-operation structural invariants with an in-memory exporter.

Runs scenario.authorize_and_maybe_execute() for a deny and an allow decision and
asserts:
  - invariant 1: exactly one decision span is emitted per evaluated decision;
  - invariant 2: a child execute span exists IFF the outcome permitted execution;
  - invariant 3: a `deny` leaves a decision span with NO child execute span.

Run: ../../../scratchpad/otelvenv/bin/python validate.py   (or any env with otel-sdk)
"""
import sys
from dataclasses import replace

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)

import scenario  # noqa: E402  (tracer must resolve against the provider set above)
scenario.tracer = trace.get_tracer("agent-authorization-scenario")


def run(outcome: str):
    exporter.clear()
    gate = scenario.Gate()
    base = gate.decide("database.read")
    gate.decide = lambda cap, d=replace(base, outcome=outcome, reason=None if outcome == "allow" else "capability_denied"): d
    scenario.authorize_and_maybe_execute(gate, "database.read")
    spans = exporter.get_finished_spans()
    decision = [s for s in spans if s.name.startswith("execute_authorization")]
    execute = [s for s in spans if s.name.startswith("execute_tool")]
    return decision, execute


def main():
    failures = []

    dec, ex = run("deny")
    if len(dec) != 1:
        failures.append(f"deny: expected 1 decision span, got {len(dec)}")
    if dec and dec[0].attributes.get("gen_ai.agent.authorization.outcome") != "deny":
        failures.append("deny: outcome attribute not 'deny'")
    if len(ex) != 0:
        failures.append(f"deny: expected 0 child execute spans (invariant 3), got {len(ex)}")
    print(f"deny  -> decision spans={len(dec)} execute spans={len(ex)}  "
          f"outcome={dec[0].attributes.get('gen_ai.agent.authorization.outcome') if dec else None}")

    dec, ex = run("allow")
    if len(dec) != 1:
        failures.append(f"allow: expected 1 decision span, got {len(dec)}")
    if len(ex) != 1:
        failures.append(f"allow: expected 1 child execute span (invariant 2), got {len(ex)}")
    print(f"allow -> decision spans={len(dec)} execute spans={len(ex)}  "
          f"outcome={dec[0].attributes.get('gen_ai.agent.authorization.outcome') if dec else None}")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("\nOK: invariants 1-3 hold for deny and allow.")


if __name__ == "__main__":
    main()
