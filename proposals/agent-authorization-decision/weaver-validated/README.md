# Weaver-validated decision operation

This directory holds the **Weaver-validating** version of the decision-operation proposal:
the actual `model/` + reference-framework changes needed in
`open-telemetry/semantic-conventions-genai`, plus a runnable reference scenario that passes
the repo's `weaver registry live-check`.

Built and validated 2026-07-02 against a checkout of the #291 fork branch
(`thebenignhacker/semantic-conventions-genai@feat/gen-ai-agent-authorization-attrs`).

## Result

```
10:50:56 [INFO] Weaver exit code: 0
10:50:56 [INFO] Updated .../agent-authorization-decision/data.json
```

Zero live-check advice/violations. The `execute_authorization` span classified with all 12
emitted attributes; the `execute_tool` child span classified under the allow path. See
`execute-authorization-span.md` for the generated coverage report (requirement levels map
exactly: required = outcome + operation.name; conditionally-required = reason;
recommended = policy/capability/method tokens; opt-in = scores/verdict/pubkey).

## Contents

- `model-and-framework.patch` — the model + framework diff (apply on the #291 fork branch):
  - `model/gen-ai/registry.yaml` — `execute_authorization` enum member +
    `gen_ai.agent.authorization.{outcome,policy,reason}`.
  - `model/gen-ai/spans.yaml` — `gen_ai.execute_authorization.internal` span (invariants in note).
  - `model/gen-ai/metrics.yaml` — `gen_ai.agent.authorization.{decisions,duration}`.
  - `reference/src/semconv_genai/{semconv_model.py,data_files.py}` — register the span type.
  - `reference/reports/*` — regenerated coverage.
- `scenario/` — the runnable reference scenario (`scenario.py`, `pyproject.toml`, `uv.lock`,
  `data.json`). Drop under `reference/scenarios/agent-authorization-decision/`.
- `execute-authorization-span.md` — the generated coverage report.

## To reproduce

```bash
# on a checkout of the #291 fork branch
git apply model-and-framework.patch
mkdir -p reference/scenarios/agent-authorization-decision
cp scenario/* reference/scenarios/agent-authorization-decision/
make filter-upstream                     # clones + filters upstream semconv registry
cd reference && uv sync
uv run run-scenario agent-authorization-decision   # -> Weaver exit 0
uv run update-reports
```

## Status

Not submitted upstream. Held until the maintainer confirms update-#291-vs-new-issue and the
span kind (`internal` vs `server`). The fork branch `feat/agent-authorization-decision-operation`
carries the same commit locally, PR-ready.
