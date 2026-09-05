# AI Failure Agent — Phase 1: Read-only Inspector

Status: ready
Labels: ready-for-agent

## Problem Statement

When an existing CI workflow fails on a pull request, the team currently has to identify the failed job, find the relevant log evidence, inspect the pull request diff, and decide whether the failure is suitable for an automated fix. There is no bounded, repeatable diagnostic flow that produces a machine-readable conclusion without granting an agent permission to change the repository.

The current foundation proposal also combines two materially different responsibilities: diagnosing a failure and mutating the pull request. That makes the first implementation difficult to validate safely and increases the impact of a wrong hypothesis or prompt injection.

## Solution

Implement a read-only Phase 1 that reacts to a failed `workflow_run` associated with a pull request, supports only deterministically classified test failures, and invokes an Inspector through `pi-coding-agent-action`.

The Inspector receives bounded workflow and pull request context through read-only GitHub tools, produces a strict JSON `TriageReport`, and cannot checkout the PR branch, execute commands, edit files, create comments, commit, or push. The workflow validates the report and publishes a bounded, redacted input snapshot plus the validated report as artifacts, along with a concise job summary.

Phase 1 records `needs_fix` as a diagnostic recommendation only. It does not launch a Fixer or perform any repository mutation.

## User Stories

1. As a pull request author, I want a failed CI run to trigger a diagnostic workflow, so that I do not have to manually collect the first set of failure details.
2. As a pull request author, I want the diagnostic workflow to run only for failed CI runs, so that successful builds do not consume model calls.
3. As a pull request author, I want the workflow to require an associated pull request, so that unrelated branch and scheduled failures are not analyzed as pull request defects.
4. As a maintainer, I want Phase 1 to recognize only test failures, so that unsupported infrastructure, dependency, lint, and build failures are not misdiagnosed as code defects.
5. As a maintainer, I want unsupported failures to stop deterministically, so that an agent cannot invent a diagnosis for a failure class outside the phase boundary.
6. As a maintainer, I want the Inspector to receive the failed job and step identity, so that its diagnosis is anchored to the actual failure location.
7. As a maintainer, I want the Inspector to receive bounded log evidence, so that irrelevant CI noise does not dominate the diagnosis or exhaust the model context.
8. As a maintainer, I want the Inspector to receive the pull request diff, so that hypotheses can be related to the changes that introduced the failure.
9. As a maintainer, I want the Inspector to access relevant repository information through read-only tools, so that it can investigate without receiving write capability.
10. As a maintainer, I want the Inspector to avoid checking out the PR branch, so that repository-controlled agent instructions and extensions cannot change the diagnostic runtime in Phase 1.
11. As a security owner, I want the Inspector tool list to be explicit, so that write, shell, Git, checkout, and pull request mutation capabilities are unavailable by construction.
12. As a security owner, I want logs, diffs, PR text, and source excerpts to be treated as untrusted data, so that prompt-injection instructions inside those inputs are not treated as agent instructions.
13. As a security owner, I want the workflow to use read-only GitHub permissions, so that a compromised or incorrect Inspector cannot mutate repository state.
14. As an agent integrator, I want the Inspector to return one defined `TriageReport` contract, so that workflow decisions do not depend on free-form prose.
15. As an agent integrator, I want the report validator to reject missing fields, wrong types, invalid confidence values, unsupported failure types, empty evidence, and non-JSON wrappers, so that downstream steps consume only trustworthy structure.
16. As a maintainer, I want `needs_fix` to remain a recommendation rather than an authorization, so that Phase 1 cannot accidentally start an automated repair.
17. As a maintainer, I want the report to include evidence-backed hypotheses and confidence, so that I can review why the Inspector reached its conclusion.
18. As a maintainer, I want the report artifact to identify the source workflow run and attempt, so that a rerun can be distinguished from an earlier diagnosis.
19. As a maintainer, I want the job summary to show the classification, report status, confidence, and recommended action, so that I can understand the result without opening raw logs.
20. As a security owner, I want published artifacts to contain only bounded, redacted input and the validated report, so that raw logs and accidental secrets are not archived unnecessarily.
21. As a maintainer, I want a deterministic fixture failure, so that the complete diagnostic path can be tested without depending on a production defect.
22. As a maintainer, I want malformed model output to produce an explicit `invalid_report` result, so that a provider or prompt regression fails closed.
23. As a maintainer, I want exactly one Inspector invocation per workflow-run attempt, so that retries do not silently multiply model cost or produce ambiguous reports.
24. As a maintainer, I want no Fixer job to be reachable in Phase 1, so that the diagnostic rollout cannot modify an existing pull request.
25. As a future implementer, I want the Phase 1 boundary to be explicit, so that Phase 2 can add checkout, execution, validation, commit, and push as a separately reviewed security boundary.

## Implementation Decisions

- The highest test seam is the complete orchestration path: failed `workflow_run` → supported-failure gate → read-only Inspector → strict `TriageReport` validation → artifact and job summary publication.
- The trigger is `workflow_run` with `completed` events, guarded by failed conclusion, pull request association, and deterministic test-failure classification.
- Phase 1 supports only test failures. Classification that cannot be established is `unsupported` and is not delegated to the model.
- The Inspector is the only model role in this phase. The Fixer does not exist as a reachable workflow job.
- The runtime is `shaftoe/pi-coding-agent-action`, pinned to a stable release rather than a development branch.
- Provider, model, and API credentials are supplied through GitHub Variables/Secrets and are not committed as workflow values.
- The Inspector uses an explicit read-only tool allowlist covering CI status, workflow-run logs, pull request diff, and pull request discussion only when needed.
- The Inspector does not checkout the PR branch. It receives workflow and pull request identifiers plus bounded API/tool results.
- External content is delimited and described as untrusted data. Instructions found in logs, diffs, PR text, or source excerpts must be ignored.
- The Inspector output is the action's response text and must be a JSON object with no Markdown fence or surrounding prose.
- `TriageReport` contains `needs_fix`, top-level `confidence`, a `failure` object, one or more hypotheses with confidence and evidence, and a recommended action.
- The validator rejects missing fields, wrong types, confidence outside `0..1`, non-test failure types, empty descriptions, empty evidence, and non-JSON wrapper text.
- Validation failure produces `invalid_report` and prevents downstream actions.
- `needs_fix` is recorded but never controls a write-capable job in Phase 1.
- Input and output artifacts are bounded, identified by workflow-run ID and attempt, and redacted before publication. A full session transcript is not published.
- The human-facing output is a concise job summary; PR comments and review creation are deferred.
- The workflow performs one Inspector invocation per workflow-run attempt and does not automatically retry the model session.
- A manually triggerable fixture workflow produces a deterministic standard-library Python test failure and is not a required production check for ordinary changes.
- The fixture and validator provide the only new seams required for local and workflow-level verification; a custom GitHub API client is not introduced in Phase 1.
- The implementation is organized around an Inspector prompt, report schema, deterministic validator, fixture failure, and two workflows: one to create the failure and one to diagnose it.

## Testing Decisions

- Tests verify externally observable behavior at the orchestration boundary, not the internal wording of prompts or the implementation language of the validator.
- The primary end-to-end test uses the fixture failure and asserts that one Inspector invocation produces a valid report artifact and job summary with the same workflow-run identity.
- A supported failure test asserts that a recognized test failure reaches the Inspector and produces `TriageReport`.
- An unsupported failure test asserts that a non-test failure stops as `unsupported` without model output or downstream mutation.
- A validator test covers a valid report, malformed JSON, Markdown-wrapped JSON, missing fields, wrong types, confidence outside `0..1`, non-test failure type, empty hypothesis description, and empty evidence.
- A publication test asserts that only bounded, redacted input and the validated report are uploaded, and that no raw session transcript is published.
- A permissions/tooling test asserts that the Inspector workflow grants read-only GitHub permissions and exposes no write, shell, Git, checkout, commit, push, or PR-comment capability.
- A rerun test asserts that a second workflow-run attempt receives a distinct artifact identity rather than replacing the first result.
- A no-mutation test asserts that Phase 1 produces no repository diff, commit, branch update, comment, or review.
- There is no existing application test suite or workflow implementation to reuse in this repository; the fixture and orchestration boundary are the appropriate prior art for this first vertical slice.

## Out of Scope

- Fixer execution or any other write-capable agent.
- Checking out, executing, editing, committing, or pushing PR code.
- Automatic retries, repair loops, or broader validation after a fix.
- PR comments, review comments, approvals, requested changes, or new pull requests.
- Non-test failures, including lint, build, dependency, infrastructure, permissions, and runner failures.
- A custom GitHub API client.
- Full repository or full-log injection into the model context.
- Full Pi session HTML/JSONL export, session sharing, or long-term transcript archival.
- Production sandboxing such as ECS/Fargate; the read-only boundary is the Phase 1 safety mechanism.
- Model evaluation beyond the three Phase 1 outcomes: supported report, unsupported failure, and invalid report.

## Further Notes

- The accepted ADR requires diagnosis and repository mutation to remain separate boundaries: [`0001-read-only-diagnosis-before-automated-fix`](../../docs/adr/0001-read-only-diagnosis-before-automated-fix.md).
- Domain vocabulary is defined in [`CONTEXT.md`](../../CONTEXT.md): `Inspector`, `Fixer`, `TriageReport`, `Evidence`, `Supported failure`, `Fixture failure`, and `Workflow run attempt`.
- The implementation should use the action's documented response output and selective tool loading rather than inventing a second agent-runtime interface.
- Phase 2 must separately decide checkout source, command execution controls, targeted and broad test policy, iteration limits, approvals, token permissions, commit policy, and push behavior.
