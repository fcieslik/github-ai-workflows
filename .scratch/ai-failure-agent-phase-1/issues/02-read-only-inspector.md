# 02: Read-only Inspector for supported failures

**What to build:** For a supported fixture failure, invoke the pinned `pi-coding-agent-action` as a read-only Inspector and produce an accepted `TriageReport` from bounded CI and pull request evidence without checking out or mutating the pull request.

**Blocked by:** 01: Fixture failure and report boundary.

**Status:** ready-for-agent

- [ ] The Inspector runs only after the supported-failure gate and report boundary from ticket 01.
- [ ] Provider, model, and API credentials are configured through GitHub Variables/Secrets rather than committed values.
- [ ] The Inspector has an explicit allowlist of read-only GitHub tools for CI status, workflow-run logs, pull request diff, and discussion when needed.
- [ ] The Inspector does not receive checkout, shell, Git, edit, commit, push, review, or comment capabilities.
- [ ] The Inspector does not checkout the PR branch, and logs, diffs, PR text, and source excerpts are clearly treated as untrusted data.
- [ ] The prompt requests strict JSON `TriageReport` output with evidence-backed hypotheses, confidence, failure details, and recommended action.
- [ ] `needs_fix` is recorded as a recommendation only and cannot launch a Fixer or any write-capable job.
- [ ] The action is pinned to a stable release and the Inspector invocation is bounded to one attempt per workflow-run attempt.
