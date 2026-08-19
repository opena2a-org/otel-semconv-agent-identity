# Weaver-validated decision operation

This directory holds the **Weaver-validating** version of the decision-operation proposal:
the actual `model/` + reference-framework changes needed in
`open-telemetry/semantic-conventions-genai`, plus a runnable reference scenario.

Rebuilt and re-validated **2026-08-19** against `ca93747`, the current head of the #291 fork
branch (`thebenignhacker/semantic-conventions-genai@feat/gen-ai-agent-authorization-attrs`),
then **re-run from scratch later the same day** after the structural invariants were restated
on the interposition axis. The re-run was done in a clean worktree at `ca93747` with the patch
below applied and nothing else, and the regenerated patch came out byte-identical to the one
built in the working tree.

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

## Two things the re-run found in the recorded artifact

Both were invisible until the whole thing was rebuilt rather than trusted.

1. **The patch was incomplete.** Adding a `gen_ai.operation.name` member propagates into
   every weaver-generated operation-name table in the repository. `make generate-docs`
   regenerates **nine** files under `docs/gen-ai/` that the recorded patch did not carry
   (`anthropic.md`, `aws-bedrock.md`, `azure-ai-inference.md`, `gen-ai-agent-spans.md`,
   `gen-ai-events.md`, `gen-ai-metrics.md`, `gen-ai-spans.md`, `mcp.md`, `openai.md`). A PR
   carrying only the old patch would have left generated docs out of date. They are included
   now, which is why the patch went from 11 files to 18.
2. **Two of the old patch's hunks were noise.** `docs/registry/README.md` and
   `docs/registry/attributes/README.md` appeared in it only to strip their trailing newline,
   an artifact of the environment the July run used. Regenerating with the pinned weaver
   (`v0.25.1`) does not reproduce them, and they are gone.

## A third failure mode, which is not a defect in the patch

Beyond the two runner-side additions below, the run also depends on a network fetch into
weaver's own `~/.weaver/vdir_cache`. On a cold cache the live-check server does not come up
inside its readiness window and the run dies with `TimeoutError: WeaverLiveCheck did not
become ready in time` and **exit code 1**. It is worth naming because it looks like a
policy-compilation failure and is not one: run `weaver registry live-check` directly and it
reports `No after_resolution policy violation`, which is how this was told apart. Re-running
once the cache is warm succeeds. Note the contrast with the failure mode below, where the run
exits **0** while reporting violations: neither the exit code alone nor the status line alone
is a sufficient check.

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
- The `escalate` brief is spelled the same way here as in `model/registry.yaml`.

Carried in from the #461 thread later on 2026-08-19, restating all three invariants on the
**interposition** axis (an evaluation is interposed when the action could not have reached
execution except by passing it):

- Invariant 1 is tightened. It now excludes a policy evaluated over activity that has already
  completed, as well as the case where nothing was in the reachable surface. As previously
  written it admitted the first of those, which is a defect in invariant 1 rather than a
  reason to admit the shape.
- Invariant 2 gains explicit **parentage**: where a child execute span is present it is a
  DIRECT child of the decision span. That relation is the only thing in the emitted data that
  records which evaluation the execution passed through.
- Invariant 3 is restated as a closed positive claim, "span shape carries exactly one
  distinction, evaluated versus never attempted", replacing the one-directional caveat. The
  caveat form had to be widened each time another childless outcome appeared; the positive
  form is stable under adding outcomes.
- The `outcome` brief and the `allow` / `deny` member briefs follow, and the scope note gains
  the in-scope case (an interposed gate deployed not to refuse records `outcome` = `allow`)
  and the out-of-scope case, without proposing where the out-of-scope shape belongs.

## Contents

- `model-and-framework.patch`, the model + framework diff, applies to `ca93747`:
  - `model/gen-ai/registry.yaml`: `execute_authorization` enum member, the authorization
    attributes, `public_key.verification`.
  - `model/gen-ai/spans.yaml`: `gen_ai.execute_authorization.internal` (invariants + scope in
    the note).
  - `model/gen-ai/metrics.yaml`: `gen_ai.agent.authorization.{decisions,duration}`.
  - `reference/src/semconv_genai/{semconv_model.py,data_files.py}`: register the span type.
  - `docs/registry/attributes/gen-ai.md`, `docs/gen-ai/*.md` (nine files), `reference/reports/**`,
    `reference/README.md`: regenerated outputs. Regenerate with `make generate-registry`,
    `make generate-docs` and `uv run update-reports`; do not hand-edit them.
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
