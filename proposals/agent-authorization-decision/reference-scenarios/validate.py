"""Validate the decision-operation structural invariants with an in-memory exporter.

Runs the reference scenario across the outcomes and asserts:

  - invariant 1: a decision span is present iff an interposed evaluation occurred;
  - invariant 2: a child execute span exists iff the outcome permitted execution, and
    where it exists it is a DIRECT CHILD of the decision span. Parentage is what records
    that this evaluation is the one the execution passed through, so it is asserted
    rather than assumed;
  - invariant 3: span shape carries exactly one distinction, evaluated versus never
    attempted. `deny`, `escalate` and `error` are asserted to be INDISTINGUISHABLE by
    shape, so only the `outcome` attribute separates them.

It also asserts that the NON-INTERPOSED shape is rejected: an action that ran and
completed, with a policy evaluated over it afterwards as a sibling span. That shape is
out of scope, and selecting spans by name alone cannot tell it apart from an interposed
decision. The `allow` form of it is the load-bearing case, because span counts are
identical to the in-scope shape; the check below asserts it is rejected specifically by
the parentage assertion, so this never becomes a test that passes for the wrong reason.

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

PERMITTING = ("allow", "warn", "transform")
CHILDLESS = ("deny", "escalate", "error")
PARENTAGE = "not a direct child of the decision span"


def emit(emitter, outcome: str):
    """Run one emitter at one outcome and select the spans by name, as a consumer would."""
    exporter.clear()
    gate = scenario.Gate()
    base = gate.decide("database.read")
    reason = None if outcome == "allow" else f"{outcome}_reason"
    gate.decide = lambda cap, d=replace(base, outcome=outcome, reason=reason): d
    emitter(gate, "database.read")
    spans = exporter.get_finished_spans()
    decision = [s for s in spans if s.name.startswith("execute_authorization")]
    execute = [s for s in spans if s.name.startswith("execute_tool")]
    return decision, execute


def check(outcome: str, decision, execute):
    """The invariants, as a consumer of the emitted data can check them."""
    problems = []

    if len(decision) != 1:
        problems.append(f"expected 1 decision span, got {len(decision)}")
        return problems

    got = decision[0].attributes.get("gen_ai.agent.authorization.outcome")
    if got != outcome:
        problems.append(f"outcome attribute is {got!r}, not {outcome!r}")

    expected = 1 if outcome in PERMITTING else 0
    if len(execute) != expected:
        problems.append(f"expected {expected} child execute spans, got {len(execute)}")

    # Invariant 2's parentage half. Counting cannot see this: the non-interposed shape
    # emits the same span names in the same numbers.
    for ex in execute:
        parent = ex.parent
        if parent is None or parent.span_id != decision[0].context.span_id:
            problems.append(f"execute span {ex.name!r} is {PARENTAGE}")

    return problems


def main():
    failures = []

    # --- invariants 1 and 2, in scope, both directions of the permitting set ----------
    for outcome in PERMITTING:
        dec, ex = emit(scenario.authorize_and_maybe_execute, outcome)
        problems = check(outcome, dec, ex)
        failures += [f"interposed {outcome}: {p}" for p in problems]
        print(f"interposed {outcome:9s} -> decision={len(dec)} execute={len(ex)} "
              f"parented={bool(ex) and ex[0].parent is not None and dec and ex[0].parent.span_id == dec[0].context.span_id}"
              f"  {'OK' if not problems else 'FAIL'}")

    # --- invariant 3: the childless outcomes are indistinguishable by shape ----------
    shapes = {}
    for outcome in CHILDLESS:
        dec, ex = emit(scenario.authorize_and_maybe_execute, outcome)
        problems = check(outcome, dec, ex)
        failures += [f"interposed {outcome}: {p}" for p in problems]
        shapes[outcome] = (len(dec), len(ex))
        print(f"interposed {outcome:9s} -> decision={len(dec)} execute={len(ex)} "
              f" {'OK' if not problems else 'FAIL'}")

    if len(set(shapes.values())) != 1:
        failures.append(
            f"deny/escalate/error are distinguishable by span shape ({shapes}); "
            "invariant 3 claims span shape carries exactly one distinction, so this "
            "would make the shape readable as an outcome discriminator"
        )
    else:
        print(f"\nshape is identical for deny/escalate/error {shapes['deny']}, "
              "so only `outcome` separates them (invariant 3)")

    # --- the non-interposed shape is out of scope and must be rejected ---------------
    # `allow` is the load-bearing case: span NAMES and COUNTS are identical to the
    # in-scope shape, so it passes every name-only check and only parentage rejects it.
    print()
    for outcome in ("allow", "deny"):
        dec, ex = emit(scenario.evaluate_after_the_fact, outcome)
        problems = check(outcome, dec, ex)
        if not problems:
            failures.append(
                f"non-interposed {outcome}: accepted, but this shape is out of scope "
                "(invariant 1). The evaluation ran after the action completed and could "
                "not have borne on whether it ran."
            )
        print(f"non-interposed {outcome:9s} -> decision={len(dec)} execute={len(ex)} "
              f" rejected={bool(problems)}  {problems if problems else ''}")

    # Non-vacuity: the `allow` rejection must come from the parentage assertion and not
    # from a span count, or this case would pass for a reason that does not generalize.
    dec, ex = emit(scenario.evaluate_after_the_fact, "allow")
    problems = check("allow", dec, ex)
    if not any(PARENTAGE in p for p in problems):
        failures.append(
            "non-interposed allow was not rejected by the parentage assertion "
            f"(problems were {problems}); parentage is the only witness of interposition, "
            "so a rejection on any other ground does not prove it is being checked"
        )
    else:
        print("\nnon-interposed allow is rejected BY PARENTAGE, not by a span count, "
              "so the interposition witness is the thing being asserted")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("\nOK: invariants 1-3 hold, and the non-interposed shape is rejected.")


if __name__ == "__main__":
    main()
