from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_core_baseline as baseline
import verify_consumer as consumer
from validate_skills import ValidationError


class ReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "consumer.json"
        self.receipt = {
            "schema_version": 1,
            "wheel_sha256": "a" * 64,
            "results": {"installed": {"executable": "original/python", "python": "3.11.0"}},
        }
        self.enterContext(redirect_stdout(io.StringIO()))
        self.enterContext(redirect_stderr(io.StringIO()))

    def test_receipt_is_exclusive_and_unchanged_by_revalidation(self) -> None:
        consumer.emit_or_check_receipt(self.receipt, receipt_path=self.path)
        original = self.path.read_bytes()
        consumer.emit_or_check_receipt(self.receipt, check_path=self.path)
        with self.assertRaises(FileExistsError):
            consumer.emit_or_check_receipt(self.receipt, receipt_path=self.path)
        self.assertEqual(self.path.read_bytes(), original)

    def test_changed_wheel_or_environment_rejects_previous_receipt(self) -> None:
        consumer.emit_or_check_receipt(self.receipt, receipt_path=self.path)
        for field in ("wheel", "executable", "python"):
            with self.subTest(field=field):
                changed = json.loads(json.dumps(self.receipt))
                if field == "wheel":
                    changed["wheel_sha256"] = "b" * 64
                else:
                    changed["results"]["installed"][field] = "changed"
                with self.assertRaisesRegex(ValidationError, "part of its identity"):
                    consumer.emit_or_check_receipt(changed, check_path=self.path)

    def test_malformed_receipt_has_a_specific_diagnostic(self) -> None:
        self.path.write_text("not JSON", encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "not valid UTF-8 JSON"):
            consumer.emit_or_check_receipt(self.receipt, check_path=self.path)

    def test_consumer_failure_or_invalid_output_writes_no_receipt(self) -> None:
        args = ["--repo-root", str(self.root), "--core-repo", str(self.root),
                "--wheel", str(self.root / "core.whl"), "--python", sys.executable,
                "--receipt", str(self.path)]
        manifest = {"core": {"version_spec": "==0.3.0", "commit": "a" * 40}}
        for returncode, stdout in ((1, "{}"), (0, "bad JSON"), (0, "[]")):
            with self.subTest(returncode=returncode, stdout=stdout):
                with patch.object(consumer, "validate_repository", return_value=manifest), \
                     patch.object(consumer, "wheel_contract", return_value={}), \
                     patch.object(consumer.subprocess, "run", return_value=
                                  subprocess.CompletedProcess([], returncode, stdout, "")):
                    self.assertEqual(consumer.main(args), 1)
                self.assertFalse(self.path.exists())


class BaselineRunTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.enterContext(redirect_stdout(io.StringIO()))
        self.enterContext(redirect_stderr(io.StringIO()))

    def fake_external_command(self, *args: str | Path) -> None:
        # Simulate only the external venv/pip boundary. Directory creation,
        # wheel selection and receipt destinations use the real orchestration.
        if "--wheel-dir" in args:
            destination = Path(args[args.index("--wheel-dir") + 1])
            self.assertTrue(destination.is_dir())
            (destination / "rpacore-0.3.0-py3-none-any.whl").write_bytes(b"built wheel")

    def fake_verifier(self, argv: list[str]) -> int:
        wheel = Path(argv[argv.index("--wheel") + 1])
        self.assertEqual(wheel.read_bytes(), b"built wheel")
        receipt = Path(argv[argv.index("--receipt") + 1])
        with receipt.open("x", encoding="utf-8") as stream:
            json.dump({"wheel": str(wheel)}, stream)
        return 0

    def test_rerun_preserves_existing_evidence_and_uses_fresh_wheel_directory(self) -> None:
        evidence = self.root / "nested" / "evidence"
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "consumer.json").write_bytes(b"previous receipt")
        (evidence / "wheels").mkdir(parents=True, exist_ok=True)
        (evidence / "wheels" / "rpacore-stale.whl").write_bytes(b"stale wheel")
        with patch.object(baseline, "validate_repository"), \
             patch.object(baseline, "run", side_effect=self.fake_external_command), \
             patch.object(baseline.verify_consumer, "main", side_effect=self.fake_verifier):
            first = baseline.verify_baseline(self.root, self.root, evidence)
            before = first.read_bytes()
            second = baseline.verify_baseline(self.root, self.root, evidence)
        self.assertNotEqual(first.parent, second.parent)
        self.assertEqual(first.read_bytes(), before)
        self.assertTrue(second.is_file())
        self.assertEqual((evidence / "consumer.json").read_bytes(), b"previous receipt")
        self.assertEqual((evidence / "wheels" / "rpacore-stale.whl").read_bytes(), b"stale wheel")

    def test_failed_build_leaves_inspectable_run_without_success_receipt(self) -> None:
        evidence = self.root / "new" / "evidence"
        with patch.object(baseline, "validate_repository"), \
             patch.object(baseline, "run", side_effect=subprocess.CalledProcessError(7, ["pip"])), \
             patch.object(baseline.verify_consumer, "main") as verify:
            with self.assertRaises(subprocess.CalledProcessError):
                baseline.verify_baseline(self.root, self.root, evidence)
        verify.assert_not_called()
        self.assertEqual(len(list(evidence.glob("run-*"))), 1)
        self.assertFalse(list(evidence.rglob("consumer.json")))

    def test_core_ref_preserves_other_github_outputs(self) -> None:
        destination = self.root / "github-output"
        destination.write_text("existing=value\n", encoding="utf-8")
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(destination)}):
            baseline.emit_core_ref(Path(__file__).resolve().parents[1], github_output=True)
        lines = destination.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "existing=value")
        self.assertRegex(lines[1], r"^commit=[a-f0-9]{40}$")


if __name__ == "__main__":
    unittest.main()
