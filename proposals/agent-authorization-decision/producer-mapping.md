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
| Duration histogram ATTRIBUTES | **none**; `fga.latency_ms` is recorded bare (`fga_engine.go:788`, the only `Record` call on it) while the counter beside it at `:785` is attributed | `enforcement_mode`, `decision`, `reason_code`, `policy_id`, `error_class`, `event_type`, `intervention_point` (one attribute dict passed to both `counter.add` and `histogram.record`) |
| Decision-to-execution parentage | **none**; emits no execute span at all (every span it starts is `fga.*`) | **none** in #3190 (no tracer); `agt.policy.evaluate` elsewhere in the repo wraps the evaluation itself |

## What this means for the proposal

- **Genuine 2-producer overlap**, stated precisely after re-measuring on 2026-08-19:
  the decision **counter** (both attributed with the outcome), and the **duration
  histogram** as an instrument. It is NOT the histogram's attributes: AIM records
  `fga.latency_ms` with no attributes at all, so `outcome` on
  `gen_ai.agent.authorization.duration` is a **one-producer** requirement today. The
  convention currently sets it at `required` there. That is a reconciliation point on
  AIM's side and must be stated as one, exactly like the milliseconds-to-seconds gap,
  rather than presented as a signal both producers already match.
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
| `gen_ai.agent.authorization.outcome` | `fga.outcome` (counter only) | the counter name suffix AND a `decision` attribute on both instruments |
| `gen_ai.agent.authorization.policy.name` | meter `aim/fga` | `policy_id` attribute |
| `gen_ai.agent.authorization.reason` | `fga.denied_by` (counter only) | `reason_code` attribute |
| `gen_ai.agent.authorization.decisions` | `fga.decisions` | `acs_intervention_*_total` (collapse) |
| `gen_ai.agent.authorization.duration` | `fga.latency_ms` (→ s) | `acs_intervention_duration_ms` (→ s) |

## Restating the reconciliation before the outcome enum moves

The #461 thread raised narrowing `gen_ai.agent.authorization.outcome` so that it carries
the **answer** to the authorization question only, with any enforcement action recorded
separately. The public commitment on that thread was to restate this mapping before the
enum moves, because narrowing changes the cross-producer reconciliation printed in the
issue body. This is that restatement. **Verified 2026-08-19** against primary sources:
AIM `apps/backend/internal/application/fga_engine.go` on public `origin/main`, and the
merged AGT [#3190](https://github.com/microsoft/agent-governance-toolkit/pull/3190)
(merged 2026-07-01), whose `acs_intervention_*` counter names and
`acs_intervention_duration_ms` histogram were confirmed present in the repository.

Under the narrowest reading the enum becomes `allow` / `deny` / `escalate` / `error`,
and `warn` and `transform` are dropped as enforcement actions rather than answers.

| Member | AIM emits today | AGT emits today | Under narrowing |
|---|---|---|---|
| `allow` | `ALLOW` | `acs_intervention_allow_total` | unchanged |
| `deny` | `DENY` plus `DENY_ATTRIBUTE` / `DENY_CONTEXT` / `DENY_CHAIN` / `DENY_INTENT` | `acs_intervention_deny_total` | unchanged |
| `escalate` | not emitted | `acs_intervention_escalate_total` | unchanged |
| `error` | `ERROR` | not emitted | unchanged |
| `warn` | not emitted | `acs_intervention_warn_total` | **dropped**, folds into `allow` |
| `transform` | not emitted | `acs_intervention_transform_total` | **dropped**, folds into `allow` |

### What that costs, stated plainly

1. **The cost is one-sided.** Both dropped members are values AGT emits and AIM does
   not. AIM loses nothing.
2. **It makes the reconciliation less reciprocal, not more.** As the issue body states
   it, AGT collapses N counters into one keyed on `outcome`, and AIM adopts
   `warn` / `escalate` / `transform`, which it does not emit today. Narrowing removes two
   of the three members AIM was to adopt. AGT would then collapse five counters into one
   **and** lose a distinction it publishes today, while AIM's side of the exchange
   shrinks to `escalate` alone.
3. **It is lossy for AGT unless something else carries the distinction.** Narrowed,
   `warn` and `transform` both map to `outcome` = `allow`. A five-way partition becomes
   three-way, and because this is emitted data rather than spec surface, a consumer
   cannot re-partition it afterwards on a discriminator that was never emitted. This
   convention does not currently propose an attribute that would carry it.
4. **The argument for narrowing that does not rest on any producer is structural.**
   `warn` and `transform` are exactly the two members that make invariant 2's permitting
   set non-obvious: with them, "permitted execution" is `{allow, warn, transform}`;
   without them it is `{allow}`, and invariant 2 can be read straight off the outcome.
   That is a claim about this convention's own shape, not a claim about what anyone
   emits, and it is the ground any narrowing should be argued on.

### Position

**Hold.** Not because the narrowing is wrong, but because point 3 is unresolved: as
things stand it would delete a distinction the only producer emitting it publishes
today, with no attribute proposed to receive it. The precondition for moving is a
recorded home for enforcement action. The producer count for this operation is
unchanged at two, AIM and AGT.
