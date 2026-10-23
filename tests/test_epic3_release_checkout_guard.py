"""Exact-release-SHA validation on disposable/fake Git state only."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import epic3_validation_bundle as v


GOOD = "a" * 40
OTHER = "b" * 40


class TestReleaseCheckoutBinding(unittest.TestCase):
    def test_safety_branch_requires_explicit_head(self):
        with self.assertRaisesRegex(ValueError, "SAFETY_BRANCH_REQUIRES"):
            v._validate_checkout_binding(v.SAFETY_VALIDATION_BRANCH, GOOD, "")

    def test_safety_branch_accepts_only_exact_sha(self):
        v._validate_checkout_binding(
            v.SAFETY_VALIDATION_BRANCH, GOOD, GOOD,
        )
        with self.assertRaisesRegex(ValueError, "HEAD_SHA_MISMATCH"):
            v._validate_checkout_binding(
                v.SAFETY_VALIDATION_BRANCH, GOOD, OTHER,
            )

    def test_pin_must_be_full_sha_not_prefix_or_invalid(self):
        for invalid in ("abcd", "g"*40, "a"*39, "a"*41):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "FULL_40_CHAR"):
                    v._validate_checkout_binding(
                        v.SAFETY_VALIDATION_BRANCH, GOOD, invalid,
                    )

    def test_feature_branch_keeps_original_behavior(self):
        v._validate_checkout_binding(v.EXPECTED_BRANCH, GOOD, "")
        v._validate_checkout_binding(v.EXPECTED_BRANCH, GOOD, GOOD)

    def test_feature_pin_mismatch_still_rejected(self):
        with self.assertRaisesRegex(ValueError, "HEAD_SHA_MISMATCH"):
            v._validate_checkout_binding(v.EXPECTED_BRANCH, GOOD, OTHER)

    def test_never_accept_main_or_unexpected_branch(self):
        for branch in ("main", "release/random", "", "epic3-geometry-fix"):
            with self.subTest(branch=branch):
                with self.assertRaisesRegex(ValueError, "UNEXPECTED"):
                    v._validate_checkout_binding(branch, GOOD, GOOD)

    def test_unknown_git_head_rejected(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_GIT_HEAD"):
            v._validate_checkout_binding(
                v.SAFETY_VALIDATION_BRANCH, "UNKNOWN", GOOD,
            )

    def test_wrong_release_candidate_cannot_even_make_evidence_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "should-not-exist"
            argv = [
                "validation-bundle", "--dataset", str(Path(tmp)/"dataset"),
                "--output-dir", str(out),
                "--runtime-workspace", str(Path(tmp)/"runtime"),
            ]
            with (
                patch("sys.argv", argv),
                patch.object(v, "_git_branch", return_value=v.SAFETY_VALIDATION_BRANCH),
                patch.object(v, "_git_head", return_value=GOOD),
                self.assertRaisesRegex(SystemExit, "REQUIRES_EXPLICIT"),
            ):
                v.main()
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
