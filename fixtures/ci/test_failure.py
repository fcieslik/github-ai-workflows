"""Deliberate standard-library failure used by the Phase 1 workflow."""

import unittest


class FixtureFailureTest(unittest.TestCase):
    def test_fixture_failure(self) -> None:
        self.fail("deterministic fixture failure")


if __name__ == "__main__":
    unittest.main()
