# 01: Fixture failure and report boundary

**What to build:** A deterministic foundation for Phase 1: a manually triggerable `Fixture failure`, a `workflow_run` gate that admits only supported test failures associated with a pull request, and a fail-closed `TriageReport` boundary that accepts valid JSON and rejects invalid model-shaped responses.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] A standard-library test fixture produces a deterministic test failure and is not required for ordinary production changes.
- [ ] Successful runs, runs without an associated pull request, and unsupported failure classes stop without invoking the Inspector.
- [ ] Supported test failures continue through the Phase 1 path with workflow-run identity and attempt information available.
- [ ] A valid `TriageReport` is accepted only when required fields, types, confidence ranges, failure type, hypothesis descriptions, and evidence are valid.
- [ ] Malformed JSON, Markdown-wrapped JSON, missing fields, invalid types, invalid confidence, unsupported failure types, empty descriptions, and empty evidence produce `invalid_report` and stop downstream processing.
- [ ] The contract boundary has focused tests for valid and invalid external behavior.
