from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.support import make_git_source


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "preflight_ci.py"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import package_skills as PACKAGER

SPEC = importlib.util.spec_from_file_location("preflight_ci", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load preflight runner: {SCRIPT}")
PREFLIGHT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PREFLIGHT
SPEC.loader.exec_module(PREFLIGHT)


class PreflightCliTests(unittest.TestCase):
    def test_help_exposes_explicit_local_inputs_and_no_external_actions(self) -> None:
        help_text = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        for option in (
            "--repo-root",
            "--core-repo",
            "--windows-python",
            "--linux-python",
            "--wsl-distribution",
            "--output-root",
        ):
            self.assertIn(option, help_text)
        for forbidden in ("--publish", "--push", "--commit", "--tag"):
            self.assertNotIn(forbidden, help_text.casefold())

    def test_main_reports_contract_failure_without_traceback(self) -> None:
        stderr = io.StringIO()
        with patch.object(
            PREFLIGHT, "run_preflight", side_effect=PREFLIGHT.ValidationError("no WSL")
        ), redirect_stderr(stderr), redirect_stdout(io.StringIO()):
            result = PREFLIGHT.main(
                [
                    "--repo-root",
                    ".",
                    "--core-repo",
                    "../rpacore",
                    "--wsl-distribution",
                    "Ubuntu",
                ]
            )

        self.assertEqual(result, 1)
        self.assertIn("Local CI preflight failed: no WSL", stderr.getvalue())


class PreflightCommandTests(unittest.TestCase):
    def test_shared_platform_steps_are_non_frozen_and_reuse_existing_tools(self) -> None:
        paths = PREFLIGHT.PlatformPaths(
            "/repo with space/á",
            "/core with space/ç",
            "/output/windows",
            "/output/evidence",
        )

        steps = PREFLIGHT.platform_steps("python3", paths)

        self.assertEqual(len(steps), 6)
        flattened = [argument for step in steps for argument in step.argv]
        self.assertNotIn("--frozen", flattened)
        self.assertTrue(any(argument.endswith("validate_skills.py") for argument in flattened))
        self.assertTrue(any(argument.endswith("package_skills.py") for argument in flattened))
        self.assertTrue(any(argument.endswith("check_core_baseline.py") for argument in flattened))
        self.assertIn("/repo with space/á/tests", flattened)

    def test_wsl_wrapper_preserves_arguments_and_uses_process_local_git_safety(self) -> None:
        command = ("python3", "/mnt/d/repo with space/á/script.py", "value with space")

        wrapped = PREFLIGHT.wsl_command(
            "Ubuntu Test",
            command,
            repo_root="/mnt/d/repo with space/á",
            core_repo="/mnt/d/core with space/ç",
        )

        self.assertEqual(wrapped[:5], ("wsl.exe", "--distribution", "Ubuntu Test", "--exec", "env"))
        self.assertEqual(wrapped[-3:], command)
        self.assertIn("GIT_CONFIG_COUNT=2", wrapped)
        self.assertIn("GIT_CONFIG_VALUE_0=/mnt/d/repo with space/á", wrapped)

    def test_wsl_path_uses_argument_list_for_non_ascii_path(self) -> None:
        completed = subprocess.CompletedProcess([], 0, stdout="/mnt/d/repo espaço\n", stderr="")
        with patch.object(PREFLIGHT.subprocess, "run", return_value=completed) as run:
            converted = PREFLIGHT.wsl_path(Path("D:/repo espaço"), "Ubuntu")

        self.assertEqual(converted, "/mnt/d/repo espaço")
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ["wsl.exe", "--distribution", "Ubuntu", "--exec"])
        self.assertEqual(command[-1], str(Path("D:/repo espaço").resolve()))

    def test_platform_stops_when_source_changes_after_a_child(self) -> None:
        expected = PREFLIGHT.SourceState("a" * 40, True, "before")
        changed = PREFLIGHT.SourceState("a" * 40, True, "after")
        step = PREFLIGHT.Step("probe", ("python", "probe.py"))
        with patch.object(PREFLIGHT, "_run_command") as run, patch.object(
            PREFLIGHT, "source_state", return_value=changed
        ), self.assertRaisesRegex(PREFLIGHT.ValidationError, "source or index changed"):
            PREFLIGHT.run_platform(
                "Windows",
                (step,),
                PREFLIGHT._identity,
                repo_root=Path("."),
                expected_state=expected,
            )
        run.assert_called_once_with(step.argv)

    def test_platform_propagates_child_failure(self) -> None:
        step = PREFLIGHT.Step("probe", ("python", "probe.py"))
        failure = subprocess.CalledProcessError(7, step.argv)
        with patch.object(PREFLIGHT, "_run_command", side_effect=failure), patch.object(
            PREFLIGHT, "source_state"
        ) as state, self.assertRaises(subprocess.CalledProcessError):
            PREFLIGHT.run_platform(
                "Linux",
                (step,),
                PREFLIGHT._identity,
                repo_root=Path("."),
                expected_state=PREFLIGHT.SourceState("a" * 40, True, "same"),
            )
        state.assert_not_called()

    def test_wsl_cleanup_is_confined_to_named_owned_child(self) -> None:
        with patch.object(PREFLIGHT, "_run_command") as run:
            PREFLIGHT.remove_wsl_evidence(
                "Ubuntu",
                "/tmp/preflight/evidence-linux",
                "/tmp/preflight",
            )
        command = run.call_args.args[0]
        self.assertEqual(
            command,
            (
                "wsl.exe",
                "--distribution",
                "Ubuntu",
                "--exec",
                "rm",
                "-rf",
                "--",
                "/tmp/preflight/evidence-linux",
            ),
        )

        with self.assertRaisesRegex(PREFLIGHT.ValidationError, "non-owned"):
            PREFLIGHT.remove_wsl_evidence(
                "Ubuntu",
                "/tmp/other/evidence-linux",
                "/tmp/preflight",
            )


class PreflightStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_temporary = tempfile.TemporaryDirectory()
        cls.clean_source = make_git_source(Path(cls.source_temporary.name) / "source")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.source_temporary.cleanup()

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def copy_source(self) -> Path:
        destination = self.root / "source"
        shutil.copytree(self.clean_source, destination)
        return destination

    def test_source_state_detects_worktree_and_index_changes(self) -> None:
        source = self.copy_source()
        clean = PREFLIGHT.source_state(source)
        target = source / "docs" / "distribution.md"
        target.write_text(
            target.read_text(encoding="utf-8") + "\nDirty preflight probe.\n",
            encoding="utf-8",
            newline="\n",
        )
        dirty = PREFLIGHT.source_state(source)
        subprocess.run(
            ["git", "add", "docs/distribution.md"],
            cwd=source,
            check=True,
            capture_output=True,
            text=True,
        )
        staged = PREFLIGHT.source_state(source)

        self.assertFalse(clean.working_tree_dirty)
        self.assertTrue(dirty.working_tree_dirty)
        self.assertTrue(staged.working_tree_dirty)
        self.assertNotEqual(clean.fingerprint, dirty.fingerprint)
        self.assertNotEqual(dirty.fingerprint, staged.fingerprint)

    def test_default_workspace_is_removed_after_failure(self) -> None:
        source = self.copy_source()
        core = self.root / "core"
        core.mkdir()
        created: Path | None = None

        with self.assertRaisesRegex(RuntimeError, "probe"):
            with PREFLIGHT.output_workspace(None, source, core) as workspace:
                created = workspace
                (workspace / "owned.txt").write_bytes(b"owned")
                raise RuntimeError("probe")

        self.assertIsNotNone(created)
        self.assertFalse(created.exists())

    def test_explicit_external_workspace_is_retained(self) -> None:
        source = self.copy_source()
        core = self.root / "core"
        core.mkdir()
        retained = self.root / "retained"

        with PREFLIGHT.output_workspace(retained, source, core) as workspace:
            (workspace / "diagnostic.txt").write_bytes(b"retained")

        self.assertEqual((retained / "diagnostic.txt").read_bytes(), b"retained")

    def test_output_below_source_is_rejected(self) -> None:
        source = self.copy_source()
        core = self.root / "core"
        core.mkdir()
        with self.assertRaisesRegex(PREFLIGHT.ValidationError, "outside the source"):
            with PREFLIGHT.output_workspace(source / "validation-artifacts", source, core):
                self.fail("unsafe workspace should not be yielded")

    def test_candidate_identity_requires_exact_dirty_state(self) -> None:
        candidate = self.root / "candidate"
        candidate.mkdir()
        state = PREFLIGHT.SourceState("a" * 40, True, "fingerprint")
        (candidate / PREFLIGHT.INVENTORY_NAME).write_text(
            json.dumps(
                {"source": {"git_commit": state.git_commit, "working_tree_dirty": False}}
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(PREFLIGHT.ValidationError, "source identity"):
            PREFLIGHT._candidate_identity(candidate, state, "Windows")

    def test_core_clone_excludes_ignored_build_residue(self) -> None:
        source = self.copy_source()
        ignored = source / "validation-artifacts" / "stale.txt"
        ignored.parent.mkdir()
        ignored.write_bytes(b"stale")
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=source,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        destination = self.root / "core-clone"

        PREFLIGHT.clone_core_baseline(source, destination, commit)

        self.assertFalse((destination / "validation-artifacts").exists())
        actual = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=destination,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(actual, commit)

    def test_dirty_tree_native_rehearsal_compares_all_ten_assets(self) -> None:
        source = self.copy_source()
        distribution = source / "docs" / "distribution.md"
        distribution.write_text(
            distribution.read_text(encoding="utf-8") + "\nDirty preflight probe.\n",
            encoding="utf-8",
            newline="\n",
        )
        core = self.root / "core"
        core.mkdir()

        def fake_run_platform(
            name: str,
            steps: tuple[PREFLIGHT.Step, ...],
            wrapper: object,
            **kwargs: object,
        ) -> None:
            del name, wrapper, kwargs
            build = next(step for step in steps if step.label == "build portable candidate")
            output = Path(build.argv[build.argv.index("--output") + 1])
            PACKAGER.build(source, output)

        def fake_clone(source: Path, destination: Path, commit: str) -> None:
            del source, commit
            destination.mkdir()

        with patch.object(
            PREFLIGHT, "wsl_path", side_effect=lambda path, distribution: path.resolve().as_posix()
        ), patch.object(
            PREFLIGHT,
            "_capture_command",
            side_effect=("Python 3.11", "Python 3.11"),
        ), patch.object(
            PREFLIGHT, "run_platform", side_effect=fake_run_platform
        ), patch.object(
            PREFLIGHT, "validate_repository"
        ) as validate, patch.object(
            PREFLIGHT, "clone_core_baseline", side_effect=fake_clone
        ), patch.object(PREFLIGHT, "remove_wsl_evidence"):
            validate.return_value = {"core": {"commit": "a" * 40}}
            result = PREFLIGHT.run_preflight(
                source,
                core,
                windows_python=Path(sys.executable),
                linux_python="python3",
                wsl_distribution="Ubuntu",
            )

        self.assertTrue(result["source"]["working_tree_dirty"])
        self.assertEqual(len(result["assets"]), 10)


if __name__ == "__main__":
    unittest.main()
