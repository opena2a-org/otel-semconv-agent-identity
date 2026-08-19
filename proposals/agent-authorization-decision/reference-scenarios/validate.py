"""Validate the decision-operation structural invariants with an in-memory exporter.

Runs scenario.authorize_and_maybe_execute() across the outcomes and asserts:
  - invariant 1: exactly one decision span is emitted per evaluated decision;
  - invariant 2: a child execute span exists IFF the outcome permitted execution;
  - invariant 3: a `deny` leaves a decision span with NO child execute span, in that
    direction only. `escalate` and `error` are childless too, so span shape does not
    identify a denial and the `outcome` attribute is the discriminator.

Run with any environment that has the opentelemetry-sdk installed:
    python -m venv .venv && .venv/bin/pip install opentelemetry-sdk
    .venv/bin/python validate.py
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
    reason = None if outcome == "allow" else f"{outcome}_reason"
    gate.decide = lambda cap, d=replace(base, outcome=outcome, reason=reason): d
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

    # Invariant 3 is one-directional. escalate and error are childless too, so a
    # childless decision span does NOT identify a denial. This asserts the shapes are
    # INDISTINGUISHABLE and that only the outcome attribute separates them: it fails if
    # anyone reintroduces the biconditional reading by giving escalate a child span, and
    # it fails if the outcome attribute stops being set.
    shapes = {}
    for outcome in ("deny", "escalate", "error"):
        dec, ex = run(outcome)
        shapes[outcome] = (len(dec), len(ex))
        if len(dec) != 1:
            failures.append(f"{outcome}: expected 1 decision span, got {len(dec)}")
        if len(ex) != 0:
            failures.append(f"{outcome}: expected 0 child execute spans, got {len(ex)}")
        got = dec[0].attributes.get("gen_ai.agent.authorization.outcome") if dec else None
        if got != outcome:
            failures.append(f"{outcome}: outcome attribute is {got!r}, not {outcome!r}")
        print(f"{outcome:9s} -> decision spans={len(dec)} execute spans={len(ex)}  outcome={got}")

    if len(set(shapes.values())) != 1:
        failures.append(
            "deny/escalate/error are distinguishable by span shape "
            f"({shapes}); invariant 3 would then be readable as an equality"
        )
    else:
        print(f"\nspan shape is identical for deny/escalate/error {shapes['deny']}, "
              "so only `outcome` separates them")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("\nOK: invariants 1-3 hold, with invariant 3 one-directional.")


if __name__ == "__main__":
    main()
