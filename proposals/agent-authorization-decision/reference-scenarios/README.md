# Reference scenarios — decision operation

OTel SemConv requires a reference scenario showing which instrumentation captures the
attributes and how (CONTRIBUTING.md §4). Two real producers back this proposal.

## AIM (shared, public, shipped)

`agent-identity-management/apps/backend/deployments/otel-demo/` — a runnable
collector → Tempo / Prometheus / Loki → Grafana stack. The FGA engine (the PDP) emits:

- the `fga.authorize` decision span (with the optional `gen_ai.agent.*` signal attrs),
- the `fga.decisions` counter (`fga.outcome` attribute),
- the `fga.latency_ms` histogram.

The decision object (`FGAResult`) is returned by `FGAEngine.Authorize()`; the span
attributes are set from that returned decision, not from literals. This is the "real
shared public component" the maintainer asked for on #291.

`scenario.py` in this directory is a minimal, self-contained port of that emission for
the SemConv reference-report tooling — a gate whose `decide()` returns a decision object,
with the span set from the returned decision. It intentionally mirrors the upstream
reference-scenario shape (see `reference/scenarios/agent-authorization` on #291).

## AGT (independent second producer)

`microsoft/agent-governance-toolkit` [#3190](https://github.com/microsoft/agent-governance-toolkit/pull/3190)
(merged) emits the same decision as `acs_intervention_*` metrics across its Python / Rust
/ Node / .NET SDKs. Not portable into this repo, but the second independent producer that
makes the operation cross-producer rather than solo. Coordinate on-thread.

## Validation

`validate.py` runs `scenario.py` through an in-memory span exporter and asserts the three
structural invariants. Verified 2026-07-02:

```
deny  -> decision spans=1 execute spans=0  outcome=deny
allow -> decision spans=1 execute spans=1  outcome=allow
OK: invariants 1-3 hold for deny and allow.
```

Run: `python validate.py` (any env with `opentelemetry-sdk`).

## TODO before upstream submission

- [x] Prove the invariants with a runnable scenario (`validate.py`).
- [x] Wire a real scenario to the actual Weaver live-check — **done 2026-07-02, exit 0, 0 advice.**
      See `../weaver-validated/` for the model+framework patch, the runnable scenario, and the
      generated coverage report.
- [ ] Regenerate the reference report tables.
- [ ] Confirm span kind (`internal` vs `server`) with maintainers before wiring the group.
