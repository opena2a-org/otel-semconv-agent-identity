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

`validate.py` runs `scenario.py` through an in-memory span exporter and asserts the three
structural invariants, plus the exclusion of the non-interposed shape. Re-run 2026-08-19,
exit code 0:

```
interposed allow     -> decision=1 execute=1 parented=True  OK
interposed warn      -> decision=1 execute=1 parented=True  OK
interposed transform -> decision=1 execute=1 parented=True  OK
interposed deny      -> decision=1 execute=0  OK
interposed escalate  -> decision=1 execute=0  OK
interposed error     -> decision=1 execute=0  OK

shape is identical for deny/escalate/error (1, 0), so only `outcome` separates them (invariant 3)

non-interposed allow     -> decision=1 execute=1  rejected=True
non-interposed deny      -> decision=1 execute=1  rejected=True

non-interposed allow is rejected BY PARENTAGE, not by a span count, so the interposition
witness is the thing being asserted

OK: invariants 1-3 hold, and the non-interposed shape is rejected.
```

Run: `python validate.py` (any env with `opentelemetry-sdk`).

### Why the `allow` exclusion case is the load-bearing one

The non-interposed shape is an action that ran to completion with a policy evaluated over
it afterwards, as a sibling span rather than a parent. At `outcome` = `deny` a span count
already rejects it, because a refusal is not supposed to have an execute span at all. At
`outcome` = `allow` the span names and counts are IDENTICAL to the in-scope shape, so every
name-only check passes and only parentage rejects it. The validator therefore asserts not
just that the `allow` case is rejected but that the rejection comes from the parentage
check, so this can never pass for a reason that does not generalize.

Each assertion was mutation-checked. Deleting the parentage assertion, emitting the
interposed execute span as a sibling, and giving `escalate` a child execute span each turn
the run red (exit 1) naming the assertion they break; the unmutated run exits 0.

## TODO before upstream submission

- [x] Prove the invariants with a runnable scenario (`validate.py`).
- [x] Wire a real scenario to the actual Weaver live-check. See `../weaver-validated/` for the
      model+framework patch, the runnable scenario, and the generated coverage report, and
      for what the recorded July result no longer says: the run reports `status: ok` and
      exit 0 only with two additions to the pinned conformance runner, which lives in a
      different repository. Rebuilt and re-run 2026-08-19.
- [x] Regenerate the reference report tables. Regenerated 2026-08-19 from the runner.
- [ ] Confirm span kind (`internal` vs `server`) with maintainers before wiring the group.
