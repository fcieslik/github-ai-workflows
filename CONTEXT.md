# AI Failure Agent

This context describes an agent that diagnoses failures in an existing GitHub Actions workflow and, in later phases, may apply verified fixes to the pull request that caused the failure.

## Roles and contracts

**Inspector**:
A read-only diagnostic agent that examines a failed CI run and produces a validated `TriageReport`.
_Avoid_: Fixer, repair agent

**Fixer**:
An execution agent that validates an Inspector hypothesis, changes repository files, runs tests, and may commit a verified fix. It is out of scope for Phase 1.
_Avoid_: Inspector, triage agent

**TriageReport**:
The structured, machine-validated contract between diagnosis and workflow orchestration. It contains the failure, evidence-backed hypotheses, confidence, and a `needs_fix` recommendation.
_Avoid_: free-form diagnosis, agent transcript

**Evidence**:
A bounded reference to a log excerpt, changed file, or repository location that supports a hypothesis in a `TriageReport`.
_Avoid_: full repository context, raw logs

**Supported failure**:
A failure that Phase 1 can classify as a test failure and pass to the Inspector. Other failure classes are reported as unsupported and do not invoke automated diagnosis.
_Avoid_: any CI failure

**Fixture failure**:
A deliberate, reproducible test failure used to exercise the end-to-end diagnostic workflow without changing production code.
_Avoid_: fake failure, mock CI

**Workflow run attempt**:
A single execution of the failed CI workflow, identified independently from reruns so each diagnostic result remains attributable to one execution.
_Avoid_: workflow, build
