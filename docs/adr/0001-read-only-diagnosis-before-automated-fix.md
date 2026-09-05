# Read-only diagnosis before automated fix

Status: accepted

Phase 1 separates diagnosis from repository mutation: the Inspector runs with read-only GitHub tools, does not checkout the PR branch, and cannot edit, execute, commit, or push. It emits a validated `TriageReport`; the Fixer and all write operations remain out of scope until a later phase. This boundary limits the impact of prompt injection and incorrect hypotheses while the evidence-gathering path is being validated.

## Considered options

- A single agent that diagnoses and fixes in one session: rejected because an incorrect diagnosis would immediately gain write access.
- Checkout the PR and let the Inspector inspect the working tree: rejected for Phase 1 because repository-controlled `AGENTS.md`, `.pi` configuration, or extensions can influence the action runtime.

## Consequences

Phase 1 needs bounded API/tool context rather than a full checkout, and it cannot verify behavior by running the PR code. That limitation is intentional; execution and mutation are introduced only with a separate Fixer boundary.
