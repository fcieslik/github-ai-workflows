# 03: Publish diagnostic report and prove the Phase 1 boundary

**What to build:** Publish the accepted Inspector result as a bounded, redacted report artifact and concise job summary, distinguish reruns by workflow-run attempt, and verify the complete Phase 1 behavior across supported, unsupported, and invalid-report scenarios.

**Blocked by:** 02: Read-only Inspector for supported failures.

**Status:** ready-for-agent

- [ ] A valid result produces a `triage-report.json` artifact and a bounded, redacted `inspector-input.json` artifact.
- [ ] The job summary shows source run identity, attempt, failure classification, report status, confidence, and recommended action.
- [ ] Artifact identities distinguish reruns and do not overwrite the result of an earlier workflow-run attempt.
- [ ] Raw logs and full session HTML/JSONL are not published as artifacts.
- [ ] The supported fixture scenario produces one valid `TriageReport` and one Inspector invocation.
- [ ] The unsupported scenario stops without model output or downstream mutation.
- [ ] The invalid-response scenario produces `invalid_report` and no downstream action.
- [ ] End-to-end verification confirms no checkout, file edit, repository diff, branch update, comment, review, commit, push, or reachable Fixer job.
