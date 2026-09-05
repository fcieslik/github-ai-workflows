import json
import unittest

from validate_report import ReportValidationError, parse_report, validate_report


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
            "description": "The assertion is intentionally failing in the fixture.",
            "confidence": 0.87,
            "evidence": ["fixtures/ci/test_failure.py:8"],
        }
    ],
    "recommended_action": {
        "type": "code_change",
        "description": "Do not change production code for the fixture failure.",
    },
}


class ValidateReportTests(unittest.TestCase):
    def test_accepts_valid_report(self) -> None:
        self.assertEqual(validate_report(VALID_REPORT), VALID_REPORT)

    def test_rejects_malformed_json(self) -> None:
        with self.assertRaises(ReportValidationError):
            parse_report("{not json}")

    def test_rejects_markdown_wrapped_json(self) -> None:
        with self.assertRaises(ReportValidationError):
            parse_report(f"```json\n{json.dumps(VALID_REPORT)}\n```")

    def test_rejects_missing_field(self) -> None:
        report = json.loads(json.dumps(VALID_REPORT))
        del report["failure"]
        with self.assertRaises(ReportValidationError):
            validate_report(report)

    def test_rejects_invalid_types(self) -> None:
        report = json.loads(json.dumps(VALID_REPORT))
        report["needs_fix"] = "true"
        with self.assertRaises(ReportValidationError):
            validate_report(report)

    def test_rejects_confidence_outside_range(self) -> None:
        report = json.loads(json.dumps(VALID_REPORT))
        report["hypotheses"][0]["confidence"] = 1.01
        with self.assertRaises(ReportValidationError):
            validate_report(report)

    def test_rejects_unsupported_failure_type(self) -> None:
        report = json.loads(json.dumps(VALID_REPORT))
        report["failure"]["type"] = "lint_failure"
        with self.assertRaises(ReportValidationError):
            validate_report(report)

    def test_rejects_empty_description_and_evidence(self) -> None:
        for field, value in (("description", ""), ("evidence", [])):
            report = json.loads(json.dumps(VALID_REPORT))
            report["hypotheses"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ReportValidationError):
                validate_report(report)

    def test_rejects_evidence_as_a_single_string(self) -> None:
        report = json.loads(json.dumps(VALID_REPORT))
        report["hypotheses"][0]["evidence"] = "bounded log reference"
        with self.assertRaises(ReportValidationError):
            validate_report(report)

    def test_rejects_non_standard_json_and_duplicate_keys(self) -> None:
        with self.assertRaises(ReportValidationError):
            parse_report("NaN")
        with self.assertRaises(ReportValidationError):
            parse_report('{"needs_fix": true, "needs_fix": false}')


if __name__ == "__main__":
    unittest.main()
