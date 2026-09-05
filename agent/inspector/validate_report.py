"""Validate the strict JSON boundary between the Inspector and orchestration."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, NoReturn


class ReportValidationError(ValueError):
    """Raised when an external Inspector response is not a TriageReport."""


def _invalid(path: str, message: str) -> NoReturn:
    raise ReportValidationError(f"{path}: {message}")


def _object(value: Any, path: str) -> dict[str, Any]:
    if type(value) is not dict:
        _invalid(path, "expected an object")
    return value


def _keys(value: dict[str, Any], required: set[str], path: str) -> None:
    missing = required - value.keys()
    if missing:
        _invalid(path, f"missing required field(s): {', '.join(sorted(missing))}")

    unexpected = value.keys() - required
    if unexpected:
        _invalid(path, f"unexpected field(s): {', '.join(sorted(unexpected))}")


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _invalid(path, "expected a non-empty string")
    return value


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _invalid(path, "expected a number")
    if not math.isfinite(value) or not 0 <= value <= 1:
        _invalid(path, "expected a finite number in the range 0..1")
    return float(value)


def _string_list(value: Any, path: str) -> list[str]:
    if type(value) is not list or not value:
        _invalid(path, "expected a non-empty array")
    return [_string(item, f"{path}[{index}]") for index, item in enumerate(value)]


def validate_report(report: Any) -> dict[str, Any]:
    """Validate and return a TriageReport without changing its values."""

    report_object = _object(report, "report")
    _keys(
        report_object,
        {"needs_fix", "confidence", "failure", "hypotheses", "recommended_action"},
        "report",
    )

    if type(report_object["needs_fix"]) is not bool:
        _invalid("report.needs_fix", "expected a boolean")
    _number(report_object["confidence"], "report.confidence")

    failure = _object(report_object["failure"], "report.failure")
    _keys(failure, {"type", "job", "step", "test"}, "report.failure")
    if _string(failure["type"], "report.failure.type") != "test_failure":
        _invalid("report.failure.type", "must be test_failure")
    _string(failure["job"], "report.failure.job")
    _string(failure["step"], "report.failure.step")
    _string(failure["test"], "report.failure.test")

    hypotheses = report_object["hypotheses"]
    if type(hypotheses) is not list or not hypotheses:
        _invalid("report.hypotheses", "expected a non-empty array")
    for index, raw_hypothesis in enumerate(hypotheses):
        path = f"report.hypotheses[{index}]"
        hypothesis = _object(raw_hypothesis, path)
        _keys(hypothesis, {"description", "confidence", "evidence"}, path)
        _string(hypothesis["description"], f"{path}.description")
        _number(hypothesis["confidence"], f"{path}.confidence")
        _string_list(hypothesis["evidence"], f"{path}.evidence")

    action = _object(report_object["recommended_action"], "report.recommended_action")
    _keys(action, {"type", "description"}, "report.recommended_action")
    _string(action["type"], "report.recommended_action.type")
    _string(action["description"], "report.recommended_action.description")

    return report_object


def _reject_constant(value: str) -> NoReturn:
    _invalid("report", f"non-standard JSON constant {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _invalid("report", f"duplicate field: {key}")
        result[key] = value
    return result


def parse_report(text: str) -> dict[str, Any]:
    """Parse one complete JSON document and validate its TriageReport shape."""

    if not isinstance(text, str):
        _invalid("response", "expected text")
    try:
        parsed = json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except ReportValidationError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise ReportValidationError("response: invalid JSON") from error
    return validate_report(parsed)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, help="file containing the JSON response")
    parser.add_argument("--text", help="JSON response supplied directly")
    parser.add_argument("--output", type=Path, help="write the validated report as JSON")
    arguments = parser.parse_args()
    if arguments.path is not None and arguments.text is not None:
        parser.error("use either path or --text, not both")
    if arguments.path is None and arguments.text is None:
        parser.error("provide a response path or --text")
    return arguments


def main() -> int:
    arguments = _arguments()
    try:
        response = arguments.text
        if response is None:
            response = arguments.path.read_text(encoding="utf-8")
        report = parse_report(response)
    except (OSError, ReportValidationError):
        print("invalid_report")
        return 1

    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if arguments.output is not None:
        arguments.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
