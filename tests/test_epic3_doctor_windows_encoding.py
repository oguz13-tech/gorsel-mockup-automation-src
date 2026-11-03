"""Regression tests for Doctor CLI reporting on legacy Windows consoles."""
from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import factory_doctor as cli


class TestDoctorWindowsEncoding(unittest.TestCase):
    def _run(self, report: dict):
        binary = io.BytesIO()
        console = io.TextIOWrapper(
            binary, encoding="cp1254", errors="strict", write_through=True
        )
        with patch.object(cli, "parse_args", return_value=SimpleNamespace(
            runtime="C:/test", fast=True,
        )), patch.object(cli, "run_factory_doctor", return_value=report), patch(
            "sys.stdout", console
        ):
            code = cli.main()
            console.flush()
            result = binary.getvalue().decode("cp1254")
        machine_line = next(
            line for line in result.splitlines() if line.startswith("DOCTOR_JSON=")
        )
        return code, result, json.loads(machine_line[len("DOCTOR_JSON="):])

    def test_ready_warning_with_unrepresentable_unicode_is_reported(self):
        report = {
            "ready": True,
            "checks": {"runtime_root": "C:/şablon/模版"},
            "error_count": 0, "warning_count": 1, "errors": [],
            "warnings": [{
                "code": "EXAMPLE_WARNING",
                "message": "⚠️ Mask AI → kullanıcı incelemesi 🙂 解析",
            }],
        }
        code, terminal, machine = self._run(report)
        self.assertEqual(code, 0)
        self.assertIn("EXAMPLE_WARNING", terminal)
        self.assertIn("DOCTOR_JSON=", terminal)
        self.assertEqual(machine["warnings"], report["warnings"])
        self.assertIn("\\u", terminal)

    def test_blocked_critical_with_emoji_retains_exit_code_two(self):
        report = {
            "ready": False,
            "checks": {"runtime_root": "C:/çalışma"},
            "error_count": 1, "warning_count": 0,
            "errors": [{
                "code": "INPUT_MISSING",
                "message": "🛑 Girdi bulunamadı → yeniden dene",
            }],
            "warnings": [],
        }
        code, terminal, machine = self._run(report)
        self.assertEqual(code, 2)
        self.assertIn("INPUT_MISSING", terminal)
        self.assertEqual(machine["errors"], report["errors"])

    def test_ready_no_warnings_prints_success_marker_without_cp1254_error(self):
        report = {
            "ready": True, "checks": {"runtime_root": "C:/şablon"},
            "error_count": 0, "warning_count": 0,
            "errors": [], "warnings": [],
        }
        code, terminal, machine = self._run(report)
        self.assertEqual(code, 0)
        self.assertIn("Kritik sorun veya uyarı bulunmadı", terminal)
        self.assertTrue(machine["ready"])


if __name__ == "__main__":
    unittest.main()
