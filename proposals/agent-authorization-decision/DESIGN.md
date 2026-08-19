# Agent authorization/governance decision: OTel SemConv proposal (scaffold)

Status: **draft scaffold, not submitted upstream.** Prepared for
`open-telemetry/semantic-conventions-genai` following the maintainer direction on
[#291](https://github.com/open-telemetry/semantic-conventions-genai/pull/291):
model the authorization **operation**, not attributes stamped on an agent span.

## Problem

The signals a governance layer produces about an agent action, the capability being
invoked, the authority the decision was measured against, and any trust / drift / scan
inputs, are not visible to model-call or agent-level instrumentation. They are outputs
of whatever component made the allow/deny decision: a policy decision point (PDP), an
agent gateway, or a governance layer in front of the action. Stamping them onto an agent
span asks instrumentation to report values it never sees.

The unit worth modeling is therefore the **decision itself**, emitted by the deciding
component and correlated onto the trace.

## The operation

A new `gen_ai.operation.name` member, `execute_authorization`, and a matching span,
counter, and histogram. See `model/`.

- **Span** `gen_ai.execute_authorization.internal`, one span per decision.
- **Counter** `gen_ai.agent.authorization.decisions`, one increment per decision, keyed
  on the `outcome` attribute (not one counter per outcome).
- **Histogram** `gen_ai.agent.authorization.duration`, decision latency.
- **Outcome enum**: `allow`, `deny`, `warn`, `escalate`, `transform`, `error`.
- **Optional signal enrichment**: the `gen_ai.agent.{trust,drift,scan}.*`,
  `public_key.algorithm`, `capability` attributes from #291, for producers that compute
  them. Not core to the operation.

## Structural invariants

These come from the #291 thread (the deny-vs-never-attempted distinction) and are what
make the telemetry auditable.

1. A decision span is present **iff** an **interposed** evaluation occurred. An
   evaluation is interposed when the action could not have reached execution except by
   passing it.
2. A child execute span (`execute_tool`, `invoke_agent`, …) is present **iff** the
   decision permitted execution (`allow` / `warn` / `transform`), and where present it
   is a **direct child** of the decision span.
3. Span shape carries **exactly one** distinction: evaluated versus never attempted. A
   decision span is present for every interposed evaluation whatever it decided, so a
   gate that refuses a call and emits nothing is indistinguishable downstream from a
   call that never happened. Everything else is read from `outcome`.

### What each one is doing

**Invariant 1 is the scope boundary, not a formality.** Two different things produce no
span, and neither is an enum value: nothing was in the reachable surface, so there was
nothing to evaluate; or a policy was evaluated over activity that had already completed,
which could not have borne on whether that activity ran. The second case is a real
deployment shape and is excluded deliberately. See the non-goal below.

**Invariant 2's parentage half is the only witness of interposition in the emitted
data.** Nothing else distinguishes "this evaluation is what the execution passed
through" from "this evaluation happened to be recorded near it". Two traces carrying the
same span names, the same counts and the same attributes differ only in whether the
execute span is a child or a sibling. `reference-scenarios/validate.py` asserts the
parentage and rejects the sibling shape, and asserts that the rejection comes from the
parentage check rather than from a span count, because at `outcome` = `allow` the counts
are identical and every name-only check passes.

**Invariant 3 is stated as a closed positive claim on purpose.** Its previous form was a
negative caveat ("a childless span does not identify a denial"), which had to be rewritten
every time another way of producing a childless span turned up, and that had already
happened once before this revision. As a positive claim about what shape carries, it is
stable under adding outcomes: any new outcome is read from the attribute like the
existing ones.

Consequence: **"never attempted" is not an enum value.** Folding it in would require
emitting a decision for a non-event and would reintroduce the exact ambiguity the enum
removes. The distinction stays structural: `deny` = a decision span with no child
execute, "never attempted" = no decision span.

## Two independent producers (honest scope)

The genuine cross-producer overlap is the **decision counter** (both attributed with
the outcome) and the **duration histogram** as an instrument, not the signal attributes.
Re-measured 2026-08-19: it is not the histogram's attributes either. AIM records
`fga.latency_ms` bare, so `outcome` on the duration histogram is a one-producer
requirement and is a reconciliation point on AIM's side. See `producer-mapping.md` for
the exact per-producer table. Summary:

- **AIM** (`agent-identity-management`, public): emits a `fga.authorize` span,
  a `fga.decisions` counter (with `fga.outcome` attribute, already the preferred
  single-counter shape), and a `fga.latency_ms` histogram. Also emits the optional
  `gen_ai.agent.*` signal attributes on the decision span.
- **AGT** (`microsoft/agent-governance-toolkit` [#3190](https://github.com/microsoft/agent-governance-toolkit/pull/3190),
  merged): emits the decision as `acs_intervention_{allow,deny,warn,escalate,transform}_total`
  counters and an `acs_intervention_duration_ms` histogram, both carrying one shared
  attribute set (`decision`, `reason_code`, `policy_id`, `enforcement_mode`,
  `error_class`, `event_type`, `intervention_point`). Emits **none** of the signal
  attributes, and this proposal must not imply it does. The "no span" claim is scoped to
  **#3190**, which registers no tracer; the repository does ship governance spans
  elsewhere, and they wrap the evaluation rather than an execution.

## Reconciliation points (reciprocal, not one-sided)

1. **Counter shape.** AGT's per-outcome counters collapse to one counter keyed on
   `outcome`. AIM already emits this shape, so this is a change AGT makes, not AIM.
2. **Outcome enum.** Neither producer currently emits the full set. AGT has
   `warn`/`escalate`/`transform` that AIM does not emit today; AIM has an `error`
   (failed-eval) value and deny sub-reasons AGT lacks. The shared enum unions these;
   **AIM adopting `warn`/`escalate`/`transform` is a future change, stated as such.**
3. **Duration unit.** Both emit milliseconds today; the convention standardizes on
   seconds per OTel convention. A reconciliation point for both, not a current match.

## Scope / non-goals

- **Not** a cross-producer content-addressed correlation key. A recomputable
  `action_ref`-style identifier binds the convention to an external derivation profile
  and belongs in its own proposal with a single frozen, versioned profile plus
  conformance vectors, out of scope here (declined twice on #291).
- **Not** a specific producer's gate implementation. The attributes are deliberately
  producer-agnostic decision inputs.
- **Not** logs. The convention defines the span + metric shape; producers may also emit
  logs (AIM does) but the convention does not require it.
- **Not** policy evaluated over activity that has already completed. A component that
  receives reported activity and evaluates policy over it is answering the same
  question, but no answer it reaches could have prevented the action, so it has no
  execution to parent and invariant 2 does not hold for it. Admitting it would break
  invariant 2 in both directions, and the refusing direction is the worse one: a
  non-gating `deny` would be shape-identical to a real refusal while the action in fact
  ran, which inverts the property invariant 3 exists to protect. It would also mix two
  populations in the duration histogram, "how long the caller waited" against "how long
  a batch evaluation took", and that histogram is half of the cross-producer overlap
  this proposal rests on. This convention does not say where such an evaluation belongs.
  That is a question for the maintainers, below, not an answer this proposal should
  supply.

## Open questions for maintainers

- ~~Update #291 in place, or open a fresh issue for the operation?~~ **Answered on our
  side 2026-08-06.** Asked on-thread twice (2026-07-02, 2026-07-13) and unanswered for
  five weeks, so a default was stated rather than asking a third time: open a fresh issue
  for the operation and treat #291 as superseded, unless a maintainer redirects. See
  [comment 5204165524](https://github.com/open-telemetry/semantic-conventions-genai/pull/291#issuecomment-5204165524).
  The issue body is drafted and held in `ISSUE-DRAFT.md`; review on or after 2026-08-13.
- Span kind: `internal` (matches `execute_tool`) vs `server` for a standalone PDP service.
- Whether the optional signal attributes belong in this proposal at all, or should be a
  separate follow-up once the operation lands.
- Where a non-interposed policy evaluation belongs, if anywhere. This proposal excludes
  it and does not propose a home for it. Asked without a preferred answer: it may belong
  in a neighbouring operation, or it may be a producer-side detail the conventions do not
  need to model.
- Whether this operation and guardrail-style content checks should share an enforcement
  axis, or stay separate operations that happen to run in one pass on some producers.

## Why the signal attributes are not being pushed for merge

The bar the maintainer set is a real shared public component emitting the thing being
standardized. Applied honestly to what is verifiable today:

- The **decision operation** has **two** independent producers (AIM and AGT). Clears it.
- The **eight signal attributes carried from #291** have **one** (AIM,
  `agent-identity-management#324`). AGT emits none of them. Does not clear it.
- **`gen_ai.agent.public_key.verification` has none.** It was added here on 2026-08-19
  from the #461 thread, and it is the one attribute in the model that no public producer
  emits today: AIM's `fga.authorize` sets the key algorithm, trust, scan and drift, and
  no verification outcome. It is in the model because the algorithm identifier is emitted
  identically whether a signature verified, failed or was never checked, so nothing today
  can carry that outcome. It must be argued on that gap, never on a producer count.

That makes the signal group nine attributes: the eight from #291 plus the verification
outcome. Do not restate the group as "eight".

So the operation is what gets proposed, and the attributes come back later as optional
enrichment carried by whichever producers actually have them. Arguing for the attributes
on the strength of a single producer, after conceding the bar, would read as moving the
goalposts.

## Provenance

- AIM claims: verified against public `agent-identity-management` `origin/main` (`fga.authorize`
  span, `fga.decisions` counter, `fga.latency_ms` histogram; `gen_ai.agent.*` enrichment
  merged in PR #324).
- AGT claims: primary source, PR #3190 (merged), host-side OTel export across Python/Rust/
  Node/.NET, `acs_intervention_*` metrics.
- Every present-tense cross-producer claim traces to one of the above. Future-state items
  (AIM adopting warn/escalate/transform; seconds unit) are labeled as future, not current.
