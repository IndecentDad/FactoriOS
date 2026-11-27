#!/usr/bin/env python3
"""Regression tests for private build/audit status transitions (no game assets)."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Tools"))
import build_private_duo


class BuildAuditStatusTests(unittest.TestCase):
    def test_later_success_clears_prior_failure_metadata(self):
        with TemporaryDirectory() as folder:
            dist = Path(folder)
            status_file = dist / "build_private_duo_status.json"
            with (patch.object(build_private_duo, "DIST", dist),
                  patch.object(build_private_duo, "STATUS_FILE", status_file)):
                log = dist / "audit.log"
                ipa = dist / "FactorioPad.ipa"
                build_private_duo.report_status(
                    "audit-existing-ipa", "failed", "audit-existing-same-ipa",
                    log, ipa=str(ipa), audit_exit_code=1,
                )
                failed = json.loads(status_file.read_text(encoding="utf-8"))
                self.assertEqual(failed["audit_exit_code"], 1)

                build_private_duo.report_status(
                    "audit-existing-ipa", "running", "audit-existing-same-ipa",
                    log, ipa=str(ipa),
                )
                running = json.loads(status_file.read_text(encoding="utf-8"))
                self.assertNotIn("audit_exit_code", running)
                self.assertEqual(running["state"], "running")

                build_private_duo.report_status(
                    "audit-existing-ipa", "completed", "audit-existing-same-ipa",
                    log, ipa=str(ipa),
                )
                completed = json.loads(status_file.read_text(encoding="utf-8"))
                self.assertEqual(completed["state"], "completed")
                self.assertEqual(completed["ipa"], str(ipa))
                self.assertNotIn("audit_exit_code", completed)
                self.assertNotIn("exit_code", completed)

    def test_new_failure_is_not_hidden_by_prior_success(self):
        with TemporaryDirectory() as folder:
            dist = Path(folder)
            status_file = dist / "build_private_duo_status.json"
            with (patch.object(build_private_duo, "DIST", dist),
                  patch.object(build_private_duo, "STATUS_FILE", status_file)):
                log = dist / "audit.log"
                build_private_duo.report_status(
                    "audit-existing-ipa", "completed", "same", log)
                build_private_duo.report_status(
                    "audit-existing-ipa", "failed", "same", log, audit_exit_code=3)
                status = json.loads(status_file.read_text(encoding="utf-8"))
                self.assertEqual(status["state"], "failed")
                self.assertEqual(status["audit_exit_code"], 3)


if __name__ == "__main__":
    unittest.main()
