# Changelog

All notable changes to this proposal repository are documented here. Format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This repo
tracks a proposal filed upstream
([open-telemetry/semantic-conventions-genai#291](https://github.com/open-telemetry/semantic-conventions-genai/pull/291),
issue [#180](https://github.com/open-telemetry/semantic-conventions-genai/issues/180)),
so entries are dated by proposal milestone rather than release version.

## [Unreleased]

### Added

- This changelog.

## 2026-06-15 — gen_ai.agent.* namespace sync

### Changed

- Registry definitions, README, and examples aligned with upstream PR
  [semantic-conventions-genai#291](https://github.com/open-telemetry/semantic-conventions-genai/pull/291):
  agent attributes scoped under `gen_ai.agent.*`; trust/drift/scan split into
  `.score`/`.verdict` plus opaque producer-scoped `.method` token pairs;
  fail-closed verifier note added on `public_key.algorithm`. (#1)
- `fga.*` left unscoped pending the working-group namespace decision
  ([#180](https://github.com/open-telemetry/semantic-conventions-genai/issues/180)). (#1)
- `docs/REFERENCE-IMPLEMENTATION.md` keeps the pre-scoping names the AIM
  backend emits today, with a migration note: the proposal is intentionally
  ahead of the live emitter until AIM's emitter update lands. (#1)

## 2026-05-20 — Initial proposal

### Added

- Initial semantic-conventions proposal for AI agent authorization
  observability: attribute definitions in `registry/agent.yaml` and
  `registry/fga.yaml`, README rationale, and
  `docs/REFERENCE-IMPLEMENTATION.md` documenting the AIM backend as the
  reference producer.
- `examples/langchain.py`: LangChain-to-OTel bridge emitting the nine
  `agent.*` and `fga.*` attributes.
- `examples/minimal_langchain_agent.py`: minimal LangChain agent used as the
  reference implementation for the Observability Summit talk.
- `gen_ai.agent.scan.verdict` framing clarified as producer-emitted; HMA
  integration flagged as roadmap, not shipped.
