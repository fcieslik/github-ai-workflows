"""Publish bounded, redacted Inspector output and a concise job summary."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Iterable

from validate_report import parse_report


READ_ONLY_TOOLS = (
    "get_ci_status",
    "get_workflow_run_logs",
    "get_pr_diff",
    "get_issue_or_pr_thread",
)
_SUMMARY_VALUE_LIMIT = 240
_REDACTION = "[REDACTED]"


def _redact(value: Any, redaction_values: Iterable[str]) -> Any:
    values = tuple(secret for secret in redaction_values if secret)
    if isinstance(value, str):
        redacted = value
        for secret in values:
            redacted = redacted.replace(secret, _REDACTION)
        return redacted
    if isinstance(value, dict):
        return {key: _redact(item, values) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, values) for item in value]
    return value


def build_input_snapshot(
    *,
    repository: str,
    workflow: str,
    run_id: str,
    run_attempt: str,
    pull_request: str,
    redaction_values: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a metadata-only snapshot; tool payloads and transcripts are excluded."""

    snapshot = {
        "source": {
            "repository": repository,
            "workflow": workflow,
            "run_id": run_id,
            "run_attempt": run_attempt,
            "pull_request": pull_request,
        },
        "classification": "supported_test_failure",
        "read_only_tools": list(READ_ONLY_TOOLS),
        "evidence_policy": {
            "ci_status": "failed jobs and steps only",
            "workflow_run_evidence": "bounded relevant excerpts only",
            "pull_request_evidence": "bounded diff and discussion only when needed",
            "external_content": "untrusted evidence; instructions are ignored",
        },
        "publication": {
            "bounded": True,
            "raw_evidence": "not_published",
            "full_session": "not_published",
        },
    }
    return _redact(snapshot, redaction_values)


def _summary_value(value: Any, redaction_values: Iterable[str]) -> str:
    text = str(_redact(str(value), redaction_values))
    text = " ".join(text.replace("`", "").split())
    text = text.replace("|", "\\|")
    if len(text) > _SUMMARY_VALUE_LIMIT:
        return text[: _SUMMARY_VALUE_LIMIT - 1] + "…"
    return text


def render_summary(
    report: dict[str, Any],
    *,
    repository: str,
    workflow: str,
    run_id: str,
    run_attempt: str,
    pull_request: str,
    redaction_values: Iterable[str] = (),
) -> str:
    """Render only validated, bounded report fields into the job summary."""

    values = tuple(redaction_values)
    action = report["recommended_action"]
    return "\n".join(
        (
            "## AI Failure Agent — Inspector",
            "",
            f"- Repository: `{_summary_value(repository, values)}`",
            f"- Source workflow: `{_summary_value(workflow, values)}`",
            f"- Source workflow run: `{_summary_value(run_id, values)}` "
            f"(attempt `{_summary_value(run_attempt, values)}`)",
            f"- Pull request: `#{_summary_value(pull_request, values)}`",
            "- Failure classification: `test_failure`",
            "- Report status: `valid`",
            f"- Confidence: `{_summary_value(report['confidence'], values)}`",
            f"- Needs-fix recommendation: `{_summary_value(report['needs_fix'], values)}`",
            f"- Recommended action: `{_summary_value(action['type'], values)}` — "
            f"{_summary_value(action['description'], values)}",
            "- Repository mutation: `none`",
            "",
        )
    )


def publish_report(
    *,
    report_path: Path,
    input_path: Path,
    summary_path: Path,
    repository: str,
    workflow: str,
    run_id: str,
    run_attempt: str,
    pull_request: str,
    redaction_values: Iterable[str] = (),
) -> None:
    """Validate, redact, and publish the report plus metadata-only input snapshot."""

    report = parse_report(report_path.read_text(encoding="utf-8"))
    redacted_report = _redact(report, redaction_values)
    report_path.write_text(
        json.dumps(redacted_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    snapshot = build_input_snapshot(
        repository=repository,
        workflow=workflow,
        run_id=run_id,
        run_attempt=run_attempt,
        pull_request=pull_request,
        redaction_values=redaction_values,
    )
    input_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        render_summary(
            redacted_report,
            repository=repository,
            workflow=workflow,
            run_id=run_id,
            run_attempt=run_attempt,
            pull_request=pull_request,
            redaction_values=redaction_values,
        ),
        encoding="utf-8",
    )


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--pull-request", required=True)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    redaction_values = tuple(
        value
        for key, value in os.environ.items()
        if key.startswith("REDACT_VALUE_") and value
    )
    publish_report(
        report_path=arguments.report,
        input_path=arguments.input,
        summary_path=arguments.summary,
        repository=arguments.repository,
        workflow=arguments.workflow,
        run_id=arguments.run_id,
        run_attempt=arguments.run_attempt,
        pull_request=arguments.pull_request,
        redaction_values=redaction_values,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
