# Weaver-validated decision operation

This directory holds the **Weaver-validating** version of the decision-operation proposal:
the actual `model/` + reference-framework changes needed in
`open-telemetry/semantic-conventions-genai`, plus a runnable reference scenario.

Rebuilt and re-validated **2026-08-19** against `ca93747`, the current head of the #291 fork
branch (`thebenignhacker/semantic-conventions-genai@feat/gen-ai-agent-authorization-attrs`).

## Result

`uv run run-scenario agent-authorization-decision` exits 0 and reports
`scenario: reference, status: ok`, with the `execute_authorization` span classified and all
14 emitted attributes credited. The generated coverage report is
`execute-authorization-span.md`; requirement levels map exactly:

- required: `authorization.outcome`, `operation.name`
- conditionally required: `authorization.policy.version`, `authorization.reason`,
  `trust.method`, `drift.method`, `scan.method`, `public_key.verification`
- recommended: `authorization.policy.name`, `agent.capability`
- opt-in: `trust.score`, `drift.score`, `scan.verdict`, `public_key.algorithm`

**That result requires two one-line additions to the pinned conformance runner, which lives in
a different repository and cannot be carried by a PR to semantic-conventions-genai.** This is
the material adoption fact for any proposal that adds a `gen_ai.operation.name` member, and it
is stated here because it is not visible from this repo:

1. `_known_operation_names` in `policies/genai_span_validation.rego`. Without
   `execute_authorization` in that set, every decision span raises
   `genai_operation_name_unknown` as a violation. The rule's own comment says "Keep
   `_known_operation_names` in sync with model/gen-ai/registry.yaml", and it is already out of
   sync with the branch's registry, which carries the memory operations the set omits.
2. `_OPERATION_NAMES` (and `_IDENTIFYING_ATTRIBUTES`) in
   `src/genai_conformance/_coverage.py`. Without an entry mapping
   `gen_ai.execute_authorization.internal` to `{"execute_authorization"}`, the span is **silently
   dropped from the coverage data**: the run can report `ok` while
   `execute-authorization-span.md` credits no library at all. That failure mode is quiet, so it
   is worth checking the data.json rather than the status line.

Both were verified by patching a copy of the pinned checkout and re-running; neither change is
included in `model-and-framework.patch`, because neither file belongs to this repository.

## What changed since the 2026-07-02 run

The earlier artifact recorded "Weaver exit code: 0, zero live-check advice/violations" against
the branch as it stood on 2 July. That claim no longer describes an unmodified run, and the
patch itself no longer applied to the branch:

- The patch had to be rebased onto `ca93747` with a three-way merge. Four files conflicted; the
  reference framework had been refactored underneath it (`SPAN_SPECS` built by `_from_yaml`
  became a lazy `span_specs()` over a `_SPANS` mapping), so the span registration was ported
  rather than reapplied.
- `make filter-upstream` no longer exists; regeneration is `make generate-registry` and
  `make generate-docs`.
- Reference scenarios now require a `conformance.yaml`; without one the scenario is not
  discovered at all.
- Upstream tightened `execute_tool`, so the child span in the scenario now also sets
  `gen_ai.tool.call.id` and `gen_ai.tool.type`.
- The `genai_operation_name_unknown` rule described above did not exist in the older pin, which
  is why the July run reported zero advisories for a new operation name.

## Model changes in this revision

Carried in from the #461 thread, 2026-08-19:

- `gen_ai.agent.authorization.policy` renamed to `...policy.name`, and a new
  `...policy.version` (conditionally required) records the revision in force at evaluation
  time. The `policy-set:prod-v7` example is gone; it was the field carrying two things in one
  string.
- New `gen_ai.agent.public_key.verification` enum (`verified` / `failed` / `unbound` /
  `not_checked`), conditionally required wherever `public_key.algorithm` is set. The algorithm
  attribute alone is emitted identically whether a signature verified, failed, or was never
  checked.
- The three method tokens are `conditionally_required` here, matching `model/spans.yaml`. The
  previous revision of this patch carried `recommended`, so the level was stated in the model
  fragment and contradicted by the validated artifact.
- Invariant 3 is stated as one-directional. `escalate` and `error` also emit no child execute
  span, so a childless decision span does not identify a denial; the discriminator is the
  `outcome` attribute.
- The `escalate` brief is spelled the same way here as in `model/registry.yaml`.

## Contents

- `model-and-framework.patch`, the model + framework diff, applies to `ca93747`:
  - `model/gen-ai/registry.yaml`: `execute_authorization` enum member, the authorization
    attributes, `public_key.verification`.
  - `model/gen-ai/spans.yaml`: `gen_ai.execute_authorization.internal` (invariants + scope in
    the note).
  - `model/gen-ai/metrics.yaml`: `gen_ai.agent.authorization.{decisions,duration}`.
  - `reference/src/semconv_genai/{semconv_model.py,data_files.py}`: register the span type.
  - `docs/registry/**`, `reference/reports/**`, `reference/README.md`: regenerated outputs.
- `scenario/`, the runnable reference scenario (`scenario.py`, `conformance.yaml`,
  `pyproject.toml`, `uv.lock`, `data.json`). Drop under
  `reference/scenarios/agent-authorization-decision/`.
- `execute-authorization-span.md`, the generated coverage report.

## To reproduce

```bash
# on a checkout of the #291 fork branch at ca93747
git apply model-and-framework.patch
mkdir -p reference/scenarios/agent-authorization-decision
cp scenario/* reference/scenarios/agent-authorization-decision/
cd reference && uv sync
uv run run-scenario agent-authorization-decision   # status: ok, exit 0
uv run update-reports
```

Without the two conformance-runner additions above, the same commands exit 0 but report two
`genai_operation_name_unknown` violations and credit no library in the coverage report.

## Status

Not submitted upstream. #461 proposes the operation; this tree is what a PR would carry.
