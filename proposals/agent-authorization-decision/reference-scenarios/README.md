# Reference scenarios: decision operation

OTel SemConv requires a reference scenario showing which instrumentation captures the
attributes and how (CONTRIBUTING.md §4). Two real producers back this proposal.

## AIM (shared, public, shipped)

`agent-identity-management/apps/backend/deployments/otel-demo/`, a runnable
collector → Tempo / Prometheus / Loki → Grafana stack. The FGA engine (the PDP) emits:

- the `fga.authorize` decision span (with the optional `gen_ai.agent.*` signal attrs),
- the `fga.decisions` counter (`fga.outcome` attribute),
- the `fga.latency_ms` histogram.

The decision object (`FGAResult`) is returned by `FGAEngine.Authorize()`; the span
attributes are set from that returned decision, not from literals. This is the "real
shared public component" the maintainer asked for on #291.

`scenario.py` in this directory is a minimal, self-contained port of that emission for
the SemConv reference-report tooling: a gate whose `decide()` returns a decision object,
with the span set from the returned decision. It intentionally mirrors the upstream
reference-scenario shape (see `reference/scenarios/agent-authorization` on #291).

## AGT (independent second producer)

`microsoft/agent-governance-toolkit` [#3190](https://github.com/microsoft/agent-governance-toolkit/pull/3190)
(merged) emits the same decision as `acs_intervention_*` metrics across its Python / Rust
/ Node / .NET SDKs. Not portable into this repo, but the second independent producer that
makes the operation cross-producer rather than solo. Coordinate on-thread.

## Validation

`validate.py` separates the two kinds of statement the convention makes, because only one
of them is checkable from emitted data.

**Contract, asserted.** A decision span is emitted for every evaluation including
refusals; `outcome` is present and a member of the enum; `reason` is present when the
outcome is not `allow`; and `deny`, `escalate` and `error` are indistinguishable by span
shape, so the attribute is the only discriminator.

**Shape, observed and printed, never asserted.** Whether a span for the permitted action
appears beneath the decision. This is a SHOULD that applies only where the deciding
component creates that span itself. Three conformant producer shapes do not satisfy it and
must not be failed for that: a component that emits the decision alone, which is what both
public producers do today; an out-of-process gateway whose executor lands as a sibling
under stock context propagation; and any deployment where the action is instrumented by a
different producer.

The rule against emitting this operation for a policy evaluated over already-completed
activity is deliberately NOT asserted. That shape is byte-identical to a conformant
out-of-process decision, so a checker claiming to detect it would be asserting something
it cannot see. The script prints both and says so.

Re-run 2026-08-19, exit code 0:

```
permitting set agrees between convention and scenario: ['allow', 'transform', 'warn']

CONTRACT (asserted)
  allow     decision=1 outcome-attr=ok reason=ok  OK
  warn      decision=1 outcome-attr=ok reason=ok  OK
  transform decision=1 outcome-attr=ok reason=ok  OK
  deny      decision=1 outcome-attr=ok reason=ok  OK
  escalate  decision=1 outcome-attr=ok reason=ok  OK
  error     decision=1 outcome-attr=ok reason=ok  OK

  deny, escalate, error share one shape (1, 0), so only `outcome` separates them
  shape-only partition over all 6 outcomes: 2 cells
    (1, 0) -> deny, escalate, error
    (1, 1) -> allow, warn, transform

SHAPE (observed, never asserted)
  deciding component creates the action span     action-span-parented: child                  contract: OK
  decision only, action instrumented elsewhere   action-span-parented: no action span emitted contract: OK
  out-of-process gateway, executor is a sibling  action-span-parented: not a child            contract: OK
  policy evaluated after the action completed    action-span-parented: not a child            contract: OK

  All four satisfy the contract. The last is the shape the convention tells
  producers not to emit, and it is indistinguishable here from the third,
  which is why that rule is a producer duty rather than a checkable property.

OK: the contract holds for every outcome and for every producer shape.
```

Run: `python validate.py` (any env with `opentelemetry-sdk`).

### Non-vacuity

The oracle states the outcomes that permit no action independently of the scenario rather
than importing the scenario's own set, and cross-checks the two, so a drift in either one
fails instead of being silently shared. Each contract assertion was mutation-checked, with
real exit codes rather than a pipeline's: dropping the `outcome` attribute, never setting
`reason`, adding `escalate` to the scenario's permitting set, drifting the oracle's own
set, and emitting two decision spans each exit 1; baseline and restored exit 0.

The shape-only partition over all six outcomes is printed on every run and is currently
**2 cells**. That number is the reason the claim "span shape carries exactly one
distinction" was removed from the model: it was false while the parentage rule stood.
Printing it keeps it from coming back unnoticed.

## TODO before upstream submission

- [x] Prove the contract with a runnable scenario (`validate.py`).
- [x] Wire a real scenario to the actual Weaver live-check. See `../weaver-validated/` for
      the model+framework patch, the runnable scenario, and the generated coverage report,
      and for what the recorded July result no longer says: the run reports `status: ok`
      and exit 0 only with two additions to the pinned conformance runner, which lives in
      a different repository.
- [x] Regenerate the reference report tables.
- [ ] Confirm span kind (`internal` vs `server`) with maintainers before wiring the group.
      This interacts with the correlation question: if a standalone PDP is `server`, the
      action span cannot be a child of the decision under any propagation scheme.
