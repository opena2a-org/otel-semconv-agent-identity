"""Validate the decision operation's contract with an in-memory exporter.

The convention makes two kinds of statement, and they are checked differently here
because only one of them is checkable from emitted data at all.

CONTRACT, asserted, exits non-zero on failure:
  - a decision span is emitted for every evaluation, including refusals;
  - `gen_ai.agent.authorization.outcome` is present and is a member of the enum;
  - `gen_ai.agent.authorization.reason` is present when the outcome is not `allow`;
  - the outcome attribute is the only discriminator: `deny`, `escalate` and `error`
    are indistinguishable by span shape.

SHAPE, observed and printed, never asserted:
  - whether a span for the permitted action appears beneath the decision span. This is
    a SHOULD that applies only when the deciding component creates that span itself.
    Three conformant producers fail it: one that emits the decision alone (what both
    public producers do today), an out-of-process gateway whose executor is a sibling,
    and any deployment where the action is instrumented by a different producer.

The emission rule that excludes a policy evaluated over already-completed activity is a
producer duty and is deliberately NOT asserted. That shape is byte-identical to a
conformant out-of-process decision, so a checker claiming to detect it would be lying.
This file records that fact rather than encoding a check that cannot work.

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

OUTCOMES = ("allow", "warn", "transform", "deny", "escalate", "error")

# Stated here independently of the scenario, from the convention: under these outcomes no
# action proceeds. It is NOT derived from `scenario.PERMITTING`, because an oracle that
# reads its expectation out of the implementation can only ever agree with it. The two
# statements are cross-checked below, so a drift in either one fails rather than being
# silently shared.
NO_PERMITTED_ACTION = ("deny", "escalate", "error")
PERMITTING = tuple(o for o in OUTCOMES if o not in NO_PERMITTED_ACTION)


def emit(emitter, outcome: str):
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


def contract(outcome: str, decision, execute):
    """What the convention requires, and what emitted data can actually show."""
    problems = []
    if len(decision) != 1:
        problems.append(f"expected exactly 1 decision span, got {len(decision)}")
        return problems
    attrs = decision[0].attributes
    got = attrs.get("gen_ai.agent.authorization.outcome")
    if got is None:
        problems.append("outcome attribute is absent; it is `required`")
    elif got not in OUTCOMES:
        problems.append(f"outcome {got!r} is not a member of the enum")
    elif got != outcome:
        problems.append(f"outcome attribute is {got!r}, not {outcome!r}")
    if outcome != "allow" and not attrs.get("gen_ai.agent.authorization.reason"):
        problems.append("reason is absent; it is conditionally required when outcome is not `allow`")
    return problems


def parented(decision, execute):
    """Observation, not an assertion. None when there is no action span to place."""
    if not execute or not decision:
        return None
    return all(e.parent is not None and e.parent.span_id == decision[0].context.span_id
               for e in execute)


def main():
    failures = []

    if set(PERMITTING) != set(scenario.PERMITTING):
        failures.append(
            f"the convention's permitting set {sorted(PERMITTING)} and the scenario's "
            f"{sorted(scenario.PERMITTING)} disagree; one of them has drifted"
        )
        print(f"permitting set: MISMATCH {sorted(PERMITTING)} vs {sorted(scenario.PERMITTING)}\n")
    else:
        print(f"permitting set agrees between convention and scenario: {sorted(PERMITTING)}\n")

    print("CONTRACT (asserted)")
    for outcome in OUTCOMES:
        dec, ex = emit(scenario.authorize_and_maybe_execute, outcome)
        problems = contract(outcome, dec, ex)
        failures += [f"{outcome}: {p}" for p in problems]
        print(f"  {outcome:9s} decision={len(dec)} outcome-attr=ok reason=ok"
              f"  {'OK' if not problems else 'FAIL ' + '; '.join(problems)}")

    # The outcome attribute is the discriminator, so the outcomes that permit no action
    # must be indistinguishable by shape. This is the property that keeps a refusal from
    # being readable off the trace instead of off the attribute.
    shapes = {}
    for outcome in NO_PERMITTED_ACTION:
        dec, ex = emit(scenario.authorize_and_maybe_execute, outcome)
        shapes[outcome] = (len(dec), len(ex))
    if len(set(shapes.values())) != 1:
        failures.append(
            f"{', '.join(NO_PERMITTED_ACTION)} are distinguishable by span shape ({shapes}); "
            "span shape would then be readable as an outcome discriminator, which the "
            "convention says it is not"
        )
    else:
        print(f"\n  {', '.join(NO_PERMITTED_ACTION)} share one shape {shapes['deny']}, "
              "so only `outcome` separates them")

    # Span shape does NOT carry exactly one distinction. Recording the real number here
    # so the claim cannot quietly come back: with a permitted action emitted beneath the
    # decision, shape alone splits the enum in two.
    cells = {}
    for outcome in OUTCOMES:
        dec, ex = emit(scenario.authorize_and_maybe_execute, outcome)
        cells.setdefault((len(dec), len(ex)), []).append(outcome)
    print(f"  shape-only partition over all {len(OUTCOMES)} outcomes: {len(cells)} cells")
    for k, v in sorted(cells.items()):
        print(f"    {k} -> {', '.join(v)}")

    print("\nSHAPE (observed, never asserted)")
    for label, emitter in (
        ("deciding component creates the action span", scenario.authorize_and_maybe_execute),
        ("decision only, action instrumented elsewhere", scenario.decide_only),
        ("out-of-process gateway, executor is a sibling", scenario.decide_out_of_process),
        ("policy evaluated after the action completed", scenario.evaluate_after_the_fact),
    ):
        dec, ex = emit(emitter, "allow")
        problems = contract("allow", dec, ex)
        failures += [f"{label}: {p}" for p in problems]
        p = parented(dec, ex)
        note = {True: "child", False: "not a child", None: "no action span emitted"}[p]
        print(f"  {label:46s} action-span-parented: {note:22s} contract: "
              f"{'OK' if not problems else 'FAIL'}")

    print("\n  All four satisfy the contract. The last is the shape the convention tells\n"
          "  producers not to emit, and it is indistinguishable here from the third,\n"
          "  which is why that rule is a producer duty rather than a checkable property.")

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("\nOK: the contract holds for every outcome and for every producer shape.")


if __name__ == "__main__":
    main()
