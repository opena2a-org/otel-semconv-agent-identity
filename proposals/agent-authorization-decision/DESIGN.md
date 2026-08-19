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

These are the load-bearing part of the design. They come directly from the #291 thread
(the deny-vs-never-attempted distinction) and are what make the telemetry auditable.

1. A decision span is present **iff** the gate evaluated something.
2. A child execute span (`execute_tool`, `invoke_agent`, …) is present **iff** the
   decision permitted execution (`allow` / `warn` / `transform`).
3. A `deny` is a present span with **no** child execute span. A blocked call that emits
   nothing is indistinguishable downstream from a call that never happened.

   Invariant 3 is one-directional and must not be read as an equality. `escalate` and
   `error` also emit no child execute span (invariant 2 permits execution only for
   `allow` / `warn` / `transform`), so "a decision span with no child" does not identify
   a denial. The discriminator between outcomes is the `outcome` attribute; span shape
   only separates "evaluated" from "never attempted".

Consequence: **"never attempted" is not an enum value.** If nothing was in the reachable
surface, no decision was made, so there is no span and no `outcome`. Folding that into
the enum would require emitting a decision for a non-event and reintroduce the exact
ambiguity the enum is meant to remove. The distinction is preserved structurally:
`deny` = a decision span with no child execute; "never attempted" = no decision span.

## Two independent producers (honest scope)

The genuine cross-producer overlap is the **decision counter + duration histogram**
(plus outcome), not the signal attributes. See `producer-mapping.md` for the exact
per-producer table. Summary:

- **AIM** (`agent-identity-management`, public): emits a `fga.authorize` span,
  a `fga.decisions` counter (with `fga.outcome` attribute, already the preferred
  single-counter shape), and a `fga.latency_ms` histogram. Also emits the optional
  `gen_ai.agent.*` signal attributes on the decision span.
- **AGT** (`microsoft/agent-governance-toolkit` [#3190](https://github.com/microsoft/agent-governance-toolkit/pull/3190),
  merged): emits the decision as `acs_intervention_{allow,deny,warn,escalate,transform}_total`
  counters and an `acs_intervention_duration_ms` histogram. Emits **none** of the signal
  attributes, and this proposal must not imply it does.

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

## Why the eight attributes are not being pushed for merge

The bar the maintainer set is a real shared public component emitting the thing being
standardized. Applied honestly to what is verifiable today:

- The **decision operation** has **two** independent producers (AIM and AGT). Clears it.
- The **eight signal attributes** have **one** (AIM, `agent-identity-management#324`).
  AGT emits none of them. Does not clear it.

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
