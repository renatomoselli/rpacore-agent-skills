"""Reference consumers of the selected installed Core wheel; no source imports."""
from __future__ import annotations

import hashlib
from importlib import metadata
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rpacore import (
    BusinessException, DefinitionIdentityError, Engine, ProcessContext,
    Status, Step, SystemException, Transaction, atomic_output_path,
    execute_transaction, load_transaction, query_transactions,
    resume_transaction, serialize_transaction,
)

DEFINITION = "companion-reference/v1"
logging.disable(logging.CRITICAL)


def environment() -> dict[str, str]:
    # Child processes must use the installed wheel, not inherited Python paths.
    # Disable ambient pytest plugins so the generated project's own tests are
    # the only test extensions involved; leave ordinary OS settings intact.
    env = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME"):
        env.pop(key, None)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    return env


class Prepare(Step):
    def execute(self, ctx: ProcessContext) -> None:
        ctx.state["prepared_count"] = ctx.state.get("prepared_count", 0) + 1
        ctx.state["value"] = "verified output"


class Publish(Step):
    def __init__(self, *, interrupt: bool = False) -> None:
        super().__init__("publish", 2)
        self.interrupt = interrupt

    def execute(self, ctx: ProcessContext) -> None:
        destination = Path(str(ctx.config["destination"]))
        expected = {"operation": ctx.transaction.id, "value": ctx.state["value"]}
        if destination.exists():
            if json.loads(destination.read_text(encoding="utf-8")) != expected:
                raise BusinessException("Conflicting output", action=self.name)
        else:
            with atomic_output_path(destination) as temporary:
                Path(temporary).write_text(json.dumps(expected), encoding="utf-8")
        if self.interrupt:
            os._exit(77)  # Real process termination after effect, before checkpoint.
        ctx.state["published"] = True


def steps(*, interrupt: bool = False) -> list[Step]:
    return [Prepare("prepare", 1), Publish(interrupt=interrupt)]


def worker(root: Path, mode: str) -> None:
    db = str(root / "transactions.db")
    if mode == "start":
        tx = Transaction(id="reference-job", reference="reference-job",
                         definition_identity=DEFINITION, steps=steps(interrupt=True))
    else:
        tx = resume_transaction("reference-job", steps(), db_path=db,
                                definition_identity=DEFINITION)
    execute_transaction(tx, transaction_db_path=db,
                        config={"destination": str(root / "output.json")})
    if tx.status is not Status.SUCCESSFUL:
        raise RuntimeError(f"Reference job ended {tx.status}")


class ConsumerScenarios(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="skills-consumer-")
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def command(self, args: list[str], *, cwd: Path | None = None,
                expected: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(args, cwd=cwd or self.root, env=environment(),
                                capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def start_interrupted(self) -> Path:
        self.command([sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                      "worker", str(self.root), "start"], expected=77)
        return self.root / "transactions.db"

    def test_generated_project_runs_tests_and_persists_output(self) -> None:
        # This is intentionally a contract test for the exact manifest baseline.
        # Revisit these scaffold expectations when selecting a different Core.
        cli = Path(sys.executable).parent / ("rpacore.exe" if os.name == "nt" else "rpacore")
        self.command([str(cli), "init", "consumer-project"])
        project = self.root / "consumer-project"
        self.assertTrue((project / "steps" / "greeting.py").is_file())
        # Keep pytest fixtures inside this scenario; a shared per-user pytest
        # temp directory may belong to a different Windows execution principal.
        self.command([sys.executable, "-B", "-m", "pytest", "-q", "-p",
                      "no:cacheprovider", "--basetemp", str(self.root / "pytest-temp"),
                      "tests"], cwd=project)
        self.command([str(cli), "run"], cwd=project)
        self.assertEqual((project / "greeting.txt").read_text(encoding="utf-8"), "Hello, Alice\n")
        page = query_transactions(str(project / "rpacore.db"))
        self.assertEqual(len(page.transactions), 1)
        saved = load_transaction(page.transactions[0].id, str(project / "rpacore.db"), readonly=True)
        self.assertIs(saved.status, Status.SUCCESSFUL)
        self.assertEqual(saved.artifacts[0].name, "greeting")

    def test_new_process_recovers_after_external_publication(self) -> None:
        db = self.start_interrupted()
        interrupted = load_transaction("reference-job", str(db), readonly=True)
        self.assertIs(interrupted.steps[0].status, Status.SUCCESSFUL)
        self.assertIs(interrupted.steps[1].status, Status.IN_PROGRESS)
        self.assertNotIn("published", interrupted.state)
        original = (self.root / "output.json").read_bytes()
        for _ in range(2):
            self.command([sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                          "worker", str(self.root), "resume"])
        saved = load_transaction("reference-job", str(db), readonly=True)
        self.assertIs(saved.status, Status.SUCCESSFUL)
        self.assertEqual(saved.state["prepared_count"], 1)
        self.assertTrue(saved.state["published"])
        self.assertEqual((self.root / "output.json").read_bytes(), original)

    def test_mismatched_definition_preserves_durable_record(self) -> None:
        db = self.start_interrupted()
        before = serialize_transaction(load_transaction("reference-job", str(db), readonly=True))
        with self.assertRaises(DefinitionIdentityError):
            resume_transaction("reference-job", steps(), db_path=str(db),
                               definition_identity="different-definition/v2")
        after = serialize_transaction(load_transaction("reference-job", str(db), readonly=True))
        self.assertEqual(after, before)

    def test_conflicting_publication_is_not_acknowledged(self) -> None:
        db = self.start_interrupted()
        (self.root / "output.json").write_text('{"operation":"other","value":"conflict"}', encoding="utf-8")
        tx = resume_transaction("reference-job", steps(), db_path=str(db),
                                definition_identity=DEFINITION)
        execute_transaction(tx, transaction_db_path=str(db),
                            config={"destination": str(self.root / "output.json")})
        saved = load_transaction(tx.id, str(db), readonly=True)
        self.assertIs(saved.status, Status.FAILED)
        self.assertEqual(saved.outcome_category.value, "business_failed")
        self.assertNotIn("published", saved.state)

    def test_business_and_system_failures_keep_distinct_outcomes(self) -> None:
        for error_type, category in ((BusinessException, "business_failed"),
                                     (SystemException, "system_failed")):
            with self.subTest(category=category):
                class Reject(Step):
                    def execute(self, ctx: ProcessContext) -> None:
                        raise error_type("Controlled failure", action=self.name)
                tx = Transaction(reference=category, steps=[Reject("reject", 1)])
                Engine().run(ProcessContext(transaction=tx))
                self.assertIs(tx.status, Status.FAILED)
                self.assertEqual(tx.outcome_category.value, category)


def verify_install(expected: dict) -> dict:
    import rpacore
    distribution = metadata.distribution("rpacore")
    if distribution.version != expected["version"]:
        raise RuntimeError("Installed Core version does not match manifest")
    origin = Path(rpacore.__file__).resolve()
    if origin != Path(distribution.locate_file("rpacore/__init__.py")).resolve():
        raise RuntimeError("Core is shadowed by an unrelated import path")
    for relative, digest in expected["files"].items():
        actual = Path(distribution.locate_file(relative)).read_bytes()
        if hashlib.sha256(actual).hexdigest() != digest:
            raise RuntimeError(f"Installed Core differs from selected wheel: {relative}")
    return {"version": distribution.version, "origin": str(origin),
            "python": sys.version.split()[0], "executable": sys.executable,
            "pytest": metadata.version("pytest")}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        worker(Path(sys.argv[2]), sys.argv[3])
    else:
        identity = verify_install(json.load(sys.stdin))
        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(ConsumerScenarios))
        print(json.dumps({"installed": identity, "tests_run": result.testsRun,
                          "failures": len(result.failures), "errors": len(result.errors),
                          "skipped": len(result.skipped)}))
        raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
