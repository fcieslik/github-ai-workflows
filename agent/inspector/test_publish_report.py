import json
import tempfile
import unittest
from pathlib import Path

from publish_report import build_input_snapshot, publish_report
from validate_report import ReportValidationError


VALID_REPORT = {
    "needs_fix": True,
    "confidence": 0.87,
    "failure": {
        "type": "test_failure",
        "job": "unit-tests",
        "step": "Run tests",
        "test": "test_create_user",
    },
    "hypotheses": [
        {
            "description": "The fixture assertion fails deterministically.",
            "confidence": 0.87,
            "evidence": ["fixtures/ci/test_failure.py:8"],
        }
    ],
    "recommended_action": {
        "type": "code_change",
        "description": "Inspect the fixture before changing production code.",
    },
}


class PublishReportTests(unittest.TestCase):
    def test_input_snapshot_is_bounded_and_redacts_values(self) -> None:
        snapshot = build_input_snapshot(
            repository="octo/example",
            workflow="Fixture CI",
            run_id="12345",
            run_attempt="2",
            pull_request="17",
            redaction_values=("Fixture CI",),
        )

        self.assertEqual(snapshot["source"]["run_id"], "12345")
        self.assertEqual(snapshot["source"]["workflow"], "[REDACTED]")
        self.assertEqual(snapshot["publication"]["raw_evidence"], "not_published")
        self.assertEqual(snapshot["publication"]["full_session"], "not_published")
        self.assertNotIn("raw_log_content", json.dumps(snapshot).lower())

    def test_publish_writes_redacted_report_and_concise_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "report.json"
            input_path = root / "input.json"
            summary_path = root / "summary.md"
            report_path.write_text(json.dumps(VALID_REPORT), encoding="utf-8")

            publish_report(
                report_path=report_path,
                input_path=input_path,
                summary_path=summary_path,
                repository="octo/example",
                workflow="Fixture CI",
                run_id="12345",
                run_attempt="2",
                pull_request="17",
                redaction_values=("unit-tests",),
            )

            published_report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(published_report["failure"]["job"], "[REDACTED]")
            self.assertEqual(json.loads(input_path.read_text(encoding="utf-8"))["source"]["run_attempt"], "2")
            summary = summary_path.read_text(encoding="utf-8")
            self.assertIn("Repository: `octo/example`", summary)
            self.assertIn("Source workflow run: `12345` (attempt `2`)", summary)
            self.assertIn("Report status: `valid`", summary)
            self.assertIn("Confidence: `0.87`", summary)
            self.assertIn("Recommended action: `code_change`", summary)

    def test_invalid_report_stops_before_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "report.json"
            input_path = root / "input.json"
            summary_path = root / "summary.md"
            report_path.write_text('{"needs_fix": true}', encoding="utf-8")

            with self.assertRaises(ReportValidationError):
                publish_report(
                    report_path=report_path,
                    input_path=input_path,
                    summary_path=summary_path,
                    repository="octo/example",
                    workflow="Fixture CI",
                    run_id="12345",
                    run_attempt="1",
                    pull_request="17",
                )

            self.assertFalse(input_path.exists())
            self.assertFalse(summary_path.exists())


if __name__ == "__main__":
    unittest.main()
