# AI Failure Agent — Phase 1: Read-only Inspector

This plan narrows [`ai_failure_agent_v1_foundation.md`](./ai_failure_agent_v1_foundation.md) to a safe, testable first implementation.

## Outcome

When a supported test failure occurs in an existing CI workflow for a pull request, GitHub Actions invokes a read-only Inspector and publishes a validated diagnostic report. Phase 1 must not modify repository files, run arbitrary commands, create comments, create commits, or push to the PR.

The phase is complete when the workflow can reliably distinguish:

1. a supported test failure and produce a valid `TriageReport`;
2. an unsupported failure and stop without invoking automated diagnosis;
3. an invalid model response and stop with `invalid_report`.

## Architecture

```text
Existing CI workflow
        │
        ▼
workflow_run: completed
        │
        ├── conclusion != failure ───────────────► END
        ├── no associated PR ─────────────────────► END
        └── failure not classified as test ───────► unsupported
        │
        ▼
AI Failure Agent workflow
        │
        ├── collect run/PR identifiers from event metadata
        ├── invoke read-only Inspector tools
        ├── validate strict JSON response
        └── publish report artifact + job summary
```

The Inspector is run through the pinned stable release of `shaftoe/pi-coding-agent-action`. Provider, model, and API token are configured through GitHub Variables/Secrets rather than committed workflow values. The action output `response` is the only source used for the report payload; the full session transcript is not published.

## Scope

### Included

- `workflow_run` trigger with `types: [completed]`.
- Failure guard for the configured target CI workflow.
- PR association from the workflow-run event; runs without a PR are ignored.
- Test-failure classification using a small deterministic set of configured log markers.
- Bounded context collection through the action's read-only GitHub tools:
  - `get_ci_status`;
  - `get_workflow_run_logs`;
  - `get_pr_diff`;
  - `get_issue_or_pr_thread`, only if PR discussion is needed.
- Explicit `loaded_tools` allowlist; no write, shell, Git, or PR-mutation tools.
- No checkout of the PR branch. The Inspector receives event identifiers and bounded API results; PR-controlled project instructions are not loaded into its workspace.
- Strict JSON `TriageReport` validation.
- `triage-report.json` and a redacted, bounded `inspector-input.json` as artifacts.
- A concise GitHub Actions job summary containing the run identity, classification, report status, confidence, and recommended action.
- One Inspector invocation per workflow-run attempt.
- A manual fixture workflow that produces a deterministic standard-library Python test failure.

### Excluded

- Fixer execution.
- Repository checkout for the Inspector.
- Arbitrary command execution.
- File edits, commits, pushes, PR comments, and review creation.
- Automatic retries of the model session.
- Non-test failures such as lint, build, dependency, infrastructure, or permission failures.
- A custom GitHub API client.
- Full session HTML/JSONL export or session sharing.

## Workflow behavior

The AI workflow should use the following deterministic guards:

```yaml
on:
  workflow_run:
    workflows: ["Fixture CI"] # configurable target in the implementation
    types: [completed]

permissions:
  actions: read
  contents: read
  pull-requests: read
```

The job runs only when the completed run has conclusion `failure`, is associated with a PR, and the bounded failure evidence matches the configured test-failure classification. Classification that cannot be established is `unsupported`; it is not delegated to the model.

Every artifact name includes the source workflow run ID and attempt number. A rerun creates a separate artifact rather than overwriting an earlier diagnostic.

## Inspector input

The prompt must identify all external content as untrusted data and instruct the model to ignore instructions found in logs, diffs, PR text, or source files. It must include:

- repository and PR identity;
- source workflow run ID and attempt;
- failed job and step metadata;
- bounded failure log excerpts;
- bounded PR diff;
- relevant file references returned by read-only tools;
- the exact `TriageReport` contract;
- the rule that the Inspector must not modify or execute anything.

Use the action's default bounded diff/log limits in Phase 1 unless the fixture proves they are insufficient. Do not place raw logs in the published artifact; redact configured secret values before writing the bounded input snapshot.

## `TriageReport` contract

The model response must be a JSON object, not a Markdown code fence or explanatory text:

```json
{
  "needs_fix": true,
  "confidence": 0.87,
  "failure": {
    "type": "test_failure",
    "job": "unit-tests",
    "step": "Run tests",
    "test": "test_create_user"
  },
  "hypotheses": [
    {
      "description": "Email is not normalized before repository insertion",
      "confidence": 0.87,
      "evidence": [
        "tests/test_users.py:42",
        "src/users/service.py:71"
      ]
    }
  ],
  "recommended_action": {
    "type": "code_change",
    "description": "Normalize email before calling UserRepository.create()"
  }
}
```

The deterministic validator must reject missing fields, wrong types, confidence values outside `0..1`, non-`test_failure` failure types, empty descriptions, empty evidence, and any response containing non-JSON wrapper text. Validation failure produces `invalid_report` and prevents downstream actions.

`needs_fix` is a routing recommendation, not authorization to change code. Phase 1 records it but never uses it to launch a Fixer.

## Repository changes

The initial implementation should add only the following areas:

```text
.github/workflows/
├── fixture-ci.yml
└── ai-failure-agent.yml

agent/inspector/
├── prompt.md
├── schema.json
└── validate_report.py

fixtures/ci/
└── test_failure.py
```

The fixture workflow is manually triggerable and is also usable from a disposable test PR. Its Python test fails deterministically through the standard library; it must not become a required production check for ordinary changes.

## Implementation sequence

1. Add the domain glossary and ADR.
2. Add the deterministic fixture failure and verify that its CI run is observable through `workflow_run`.
3. Add the report schema and validator, including local tests for valid, malformed, incomplete, and out-of-range reports.
4. Add the AI workflow guards and read-only permissions.
5. Pin the stable `pi-coding-agent-action` release and configure provider/model/token through Variables/Secrets.
6. Configure the read-only tool allowlist and the Inspector prompt.
7. Capture the action `response`, validate it, redact and publish artifacts, then write the job summary.
8. Exercise the three acceptance scenarios and a rerun; confirm that no repository state changes.

## Acceptance criteria

- A fixture test failure invokes exactly one Inspector session for the workflow-run attempt.
- A valid response produces `triage-report.json` and a job summary with the same run identity.
- The report passes deterministic validation before publication.
- An unsupported non-test failure does not invoke the Inspector, or is explicitly recorded as `unsupported` without model output.
- A malformed model response produces `invalid_report` and no downstream action.
- The Inspector has no write, shell, Git, checkout, commit, push, or PR-comment capability.
- No PR branch instructions are loaded into the Inspector workspace.
- A rerun produces a distinct artifact.
- Published artifacts contain only bounded, redacted inputs and the validated report.
- No Fixer job is present or reachable from the Phase 1 workflow.

## Phase 2 boundary

Phase 2 may add a separate Fixer job only after Phase 1 demonstrates stable report validity and useful evidence. It must introduce its own checkout, execution, test, iteration, permission, approval, commit, and push decisions rather than extending the Inspector's permissions implicitly.
