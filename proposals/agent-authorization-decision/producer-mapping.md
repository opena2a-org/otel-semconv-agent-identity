# Producer mapping: decision operation

Honest, no-overclaim mapping of what each independent producer emits **today**. AIM
claims are verified against public `agent-identity-management` `origin/main`; AGT claims
are from primary source (PR [#3190](https://github.com/microsoft/agent-governance-toolkit/pull/3190), merged).

| Signal | AIM (public `origin/main`) | AGT (#3190, public) |
|---|---|---|
| Per-decision span | `fga.authorize` | none (metrics only) |
| Decision counter | `fga.decisions`, ONE counter + `fga.outcome` attr (meter `aim/fga`) | `acs_intervention_{allow,deny,warn,escalate,transform}_total`, N counters (meter `agent_control_specification`) |
| Duration histogram | `fga.latency_ms` (ms) | `acs_intervention_duration_ms` (ms) |
| Outcome values | `ALLOW`, `DENY`, `DENY_ATTRIBUTE`/`DENY_CONTEXT`/`DENY_CHAIN`/`DENY_INTENT`, `ERROR` (deny granularity also in `fga.denied_by`) | `allow`, `deny`, `warn`, `escalate`, `transform` |
| Signal attrs (trust/drift/scan/pubkey/capability) | yes, `gen_ai.agent.*` on the span | **none** |

## What this means for the proposal

- **Genuine 2-producer overlap** = decision counter + duration histogram (+ outcome).
  This is the core the convention standardizes.
- **NOT the signal attributes.** AGT emits none of them. They are optional, producer-
  specific enrichment. Any proposal text that implies AGT emits trust/drift/scan is wrong.
- **Counter shape**: AIM is already in the OTel-preferred single-counter-plus-`outcome`
  form; the reconciliation asks AGT to collapse its N counters. AIM gives nothing up here.
- **Outcome enum**: the shared enum is a union. AIM adopting `warn`/`escalate`/`transform`
  is a **future** change; AGT adopting `error` + deny sub-reasons is a future change on
  its side. State both as future, not current.
- **Duration unit**: both emit ms today; the convention's `s` unit is a converge-to target.

## Mapping to the proposed convention

| Proposed | AIM emits as | AGT emits as |
|---|---|---|
| `gen_ai.execute_authorization` span | `fga.authorize` | (no span yet) |
| `gen_ai.agent.authorization.outcome` | `fga.outcome` | the counter name suffix |
| `gen_ai.agent.authorization.policy.name` | meter `aim/fga` | meter `agent_control_specification` |
| `gen_ai.agent.authorization.reason` | `fga.denied_by` | (n/a) |
| `gen_ai.agent.authorization.decisions` | `fga.decisions` | `acs_intervention_*_total` (collapse) |
| `gen_ai.agent.authorization.duration` | `fga.latency_ms` (→ s) | `acs_intervention_duration_ms` (→ s) |
