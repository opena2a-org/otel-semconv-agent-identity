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

## Emission rules, and what span shape does not carry

These come from the #291 thread (the deny-versus-never-attempted distinction). They were
carried until 2026-08-19 as three numbered "structural invariants" described as the
load-bearing part of the design. That framing was wrong and is recorded here rather than
quietly dropped, because the reasoning is the useful part.

**Emission (normative).** Emit a decision span for every evaluation consulted before the
action whose answer determines whether the action proceeds, refusals included. A gate
that blocks a call and emits nothing leaves no record of the refusal, and that is the one
property this operation exists to provide. Do not emit it for a policy evaluated over
activity that has already completed; see the non-goal below.

**Correlation (SHOULD, and an open question).** Where the deciding component itself
creates the span for the permitted action, that span should sit beneath the decision.
Where it does not, the relationship is unavailable and its absence means nothing.

**Reading the outcome (informative).** `outcome` is the discriminator. `deny`, `escalate`
and `error` all produce a decision span with no permitted action beneath it, so span shape
does not identify a refusal.

Consequence, unchanged: **"never attempted" is not an enum value.** Folding it in would
require emitting a decision for a non-event and would reintroduce the exact ambiguity the
enum removes.

### Why these are not stated as invariants any more

Three statements of the form "X is present if and only if Y" were carried as normative
structure, and each of the three failed on measurement.

**The parentage biconditional was not satisfiable by anyone.** No public producer emits
the relation at all: every span AIM starts is an `fga.*` span and it emits no execute span
anywhere, and AGT's merged telemetry registers no tracer. It is not satisfiable by a
correct distributed deployment either, because parentage is written by the child's emitter
from whatever context is current in its process; a gateway that propagates normally
produces a sibling, which is the `server`-kind PDP still listed as an open question below.
Upstream has no precedent for it: the only parentage sentence in the GenAI span model is
on `gen_ai.plan.internal`, and it is a SHOULD that describes tool spans as "typically
sibling operations under the same `invoke_agent` span", which is the shape the
biconditional declared non-conformant. And `gen_ai.execute_tool` is only
`requirement_level: recommended` upstream, so a conformant producer may omit the child
entirely, which falsifies an "if and only if" outright. Upstream's conformance tooling
cannot represent span parentage at all, so nothing in the venue this would live in could
check it.

**"Span shape carries exactly one distinction" was false while the parentage rule stood.**
Child presence made shape a perfect discriminator of `allow`/`warn`/`transform` from
`deny`/`escalate`/`error`. Partitioning the outcomes on shape alone gives two cells, not
one, so the document required producers to emit a discriminator it forbade consumers to
read. `reference-scenarios/validate.py` now prints that partition on every run so the
claim cannot return unnoticed.

**The emission biconditional asked instrumentation to condition on something it cannot
observe.** Whether an evaluation could have prevented the action is a property of
deployment and timing, not of anything visible at the instrumentation point. AIM is the
example: its MEDIUM-risk path dispatches a detached, fire-and-forget intent check whose
blocked result only logs, so the same binary in the same deployment produces both gating
and non-gating evaluations depending on the policy's risk level. Asking a library to
suppress a span on grounds it never sees is the same defect #291 was rejected for,
inverted. As a SHOULD-level producer duty resting on the histogram's population, the
content survives; as a biconditional it did not.

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
  question, but no answer it reaches could have prevented the action. The reason to
  exclude it is the metric, not the trace: it would mix two populations in
  `gen_ai.agent.authorization.duration`, "how long the caller waited" against "how long
  a batch evaluation took", and the counter would merge a refusal that stopped something
  with one that did not into a single series. Nothing in the emitted data marks the
  difference, which is why this is a producer duty stated as a SHOULD NOT rather than a
  property a consumer can verify. This convention does not say where such an evaluation
  belongs. That is a question for the maintainers, below, not an answer this proposal
  should supply.

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
- **How a decision should be correlated with the action it governed.** This is the
  question the parentage rule was silently answering, and removing that rule leaves it
  open rather than settled. A recomputable content-addressed identifier was declined
  twice on #291 and stays a non-goal above. Trace parentage was the implicit alternative
  and no public producer emits it. Asked without a preferred answer: common ancestry
  under the calling operation, a span link, an explicit identifier revisited, or out of
  scope for this convention. The answer interacts with the span-kind question above: if
  a standalone PDP is `server`, parentage is structurally unavailable regardless.
- **Whether the deployment mode belongs on this operation.** A gate consulted before the
  action but deployed not to enforce records the answer it gave, so a policy that
  evaluated to `deny` records `deny` even though the action proceeded. Nothing currently
  carries the enforcing-versus-dry-run distinction, so a consumer cannot separate those
  populations. There is a producer for it (AGT emits an enforcement mode on both its
  counter and its histogram), so this is a real candidate rather than a gap invented to
  be filled.

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
