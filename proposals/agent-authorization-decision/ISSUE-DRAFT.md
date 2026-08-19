# Issue draft: `execute_authorization` decision operation

**Status: FILED 2026-08-18 as
[genai#461](https://github.com/open-telemetry/semantic-conventions-genai/issues/461).**
The body below is kept as the AS-FILED record. Do not edit it to match later decisions;
that would destroy the record of what was actually posted.

**One claim in it has since gone stale.** The validation paragraph says the patch "passes
`weaver registry live-check` with exit code 0 and zero advisories". Re-run on 2026-08-19
against `ca93747`: exit code 0 still holds, **zero advisories does not**. The current
pinned conformance runner emits two `genai_operation_name_unknown` violations for any new
`gen_ai.operation.name` member, and that rule did not exist in the pin the original run
used. See `weaver-validated/README.md` for the measurement and for the two runner-side
additions the clean result depends on. The filed issue body on GitHub carries the same
sentence and has not been edited.

**The same sentence understated a second thing, found on the 2026-08-19 rebuild.** The patch
it refers to was also incomplete: adding a `gen_ai.operation.name` member regenerates nine
`docs/gen-ai/*.md` operation-name tables that the patch did not carry. That is fixed in the
tree, and it is recorded here because the claim in the filed body is what pointed at the
patch. The tree the body links to now carries the complete, re-validated version.

**Status when drafted: 2026-08-06, NOT filed.** Held deliberately.

Intended target: a new issue on `open-telemetry/semantic-conventions-genai`.
Suggested title:

> Proposal: `execute_authorization`, an operation for agent authorization/governance decisions

## Why it is held rather than filed

On 2026-08-06 the #291 thread was rebased (conflict cleared, CI green) and a
[comment](https://github.com/open-telemetry/semantic-conventions-genai/pull/291#issuecomment-5204165524)
was posted stating this as the **default** path: open the decision operation as a fresh
issue and treat #291 as superseded, unless a maintainer redirects. Filing the issue the
same day would make "say the word if you would rather it went another way" read as
pro forma. The hold gives @lmolkova room to redirect; if there is no response, this is
filed as a stated default rather than a fait accompli.

Review date: on or after 2026-08-13.

## Claim provenance (verified 2026-08-06, primary sources, not notes)

- AGT [#3190](https://github.com/microsoft/agent-governance-toolkit/pull/3190) is
  **MERGED** (2026-07-01). Earlier internal notes recorded it as open; re-verified before
  asserting "merged" upstream. `acs_intervention_*` and `acs_intervention_duration_ms`
  confirmed present in the merged tree (implementation + docs).
- AIM `fga.authorize` / `fga.decisions` (keyed on `fga.outcome`) / `fga.latency_ms`
  confirmed in `apps/backend/internal/application/fga_engine.go` on public `origin/main`,
  not only in `OBSERVABILITY.md`.
- Both outbound links in the body below return HTTP 200. The proposal tree URL was
  checked explicitly because the branch name contains a slash.
- `opena2a-standards/otel-semconv-agent-identity` confirmed PUBLIC, so linking it from an
  OTel issue exposes no private path.

## Body (paste verbatim)

---

Following from #291 and @lmolkova's direction there: model the authorization **operation**, rather than attributes stamped on an agent span. If this lands, it supersedes #291.

## Why an operation

The signals a governance layer produces about an agent action (the capability invoked, the policy it was measured against, the outcome) are not visible to model-call or agent-level instrumentation. They are outputs of whatever component made the allow/deny decision: a policy decision point, an agent gateway, or a governance layer in front of the action. Stamping them onto an agent span asks instrumentation to report values it never sees, which was the substance of the objection on #291.

The unit worth modeling is the decision itself, emitted by the deciding component and correlated onto the trace.

## Shape

- **Span** `gen_ai.execute_authorization.internal`, one per decision, plus a new `gen_ai.operation.name` member `execute_authorization`.
- **Counter** `gen_ai.agent.authorization.decisions`, one increment per decision keyed on an `outcome` attribute, rather than one counter per outcome.
- **Histogram** `gen_ai.agent.authorization.duration`.
- **Outcome enum**: `allow`, `deny`, `warn`, `escalate`, `transform`, `error`.

## Structural invariants

These are the load-bearing part, and they came out of the deny-versus-never-attempted discussion on #291:

1. A decision span is present **iff** the gate evaluated something.
2. A child execute span is present **iff** the decision permitted execution.
3. A `deny` is a present span with **no** child execute span beneath it.

A gate that blocks a call and emits nothing is indistinguishable downstream from a call that was never made, which is what invariant 3 prevents.

Consequence: "never attempted" is not an enum value. If nothing was in the reachable surface then no decision was made, so there is no span and no `outcome` at all. Making it an enum member would require a producer to emit a decision for a non-event. The distinction stays structural instead: `deny` is a decision span with no child, "never attempted" is the absence of a decision span.

## Two independent producers

| Signal | AIM (public) | AGT ([#3190](https://github.com/microsoft/agent-governance-toolkit/pull/3190), merged) |
|---|---|---|
| Per-decision span | `fga.authorize` | none, metrics only |
| Decision counter | `fga.decisions`, one counter keyed on `fga.outcome` | `acs_intervention_{allow,deny,warn,escalate,transform}_total`, N counters |
| Duration histogram | `fga.latency_ms` | `acs_intervention_duration_ms` |
| Trust / drift / scan attributes | yes | **none** |

To be explicit about scope: the genuine cross-producer overlap is the decision counter, the duration histogram, and the outcome. It is **not** the trust/drift/scan attributes from #291. AGT emits none of those and this proposal should not imply that it does. They stay optional, producer-specific enrichment on the span.

Reconciliation runs in both directions, so this is not a request that one producer absorb the other's shape:

- AGT would collapse its per-outcome counters into one counter keyed on `outcome`. AIM already emits that shape, so it gives nothing up here.
- AIM would adopt `warn` / `escalate` / `transform`, which it does not emit today. AGT would adopt `error` and deny sub-reasons, which it lacks. Both are future changes, not current matches.
- Both emit milliseconds today. The convention's seconds unit is a converge-to target for both.

## Status

Model fragments, the per-producer mapping, and a runnable reference scenario are here: https://github.com/opena2a-standards/otel-semconv-agent-identity/tree/proposal/agent-authorization-decision/proposals/agent-authorization-decision

The model and framework patch passes `weaver registry live-check` with exit code 0 and zero advisories against a checkout of this repo. The `execute_authorization` span classifies with all emitted attributes and the `execute_tool` child classifies under the allow path. Happy to open it as a PR whenever there is a signal to.

## Open questions

- Span kind: `internal`, matching `execute_tool`, or `server` for a standalone PDP service?
- Do the optional signal attributes belong in this proposal at all, or as a follow-up once the operation lands? I am fine deferring them entirely.
