from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "package_skills.py"
SPEC = importlib.util.spec_from_file_location("package_skills", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load packager: {SCRIPT}")
PACKAGER = importlib.util.module_from_spec(SPEC)
sys.path.insert(0, str(REPO_ROOT / "scripts"))
SPEC.loader.exec_module(PACKAGER)


def make_git_source(destination: Path) -> Path:
    shutil.copytree(
        REPO_ROOT,
        destination,
        ignore=shutil.ignore_patterns(".git", "validation-artifacts", "__pycache__", "*.pyc"),
    )
    commands = (
        ("git", "init", "--quiet"),
        ("git", "config", "user.email", "distribution@example.invalid"),
        ("git", "config", "user.name", "Distribution Test"),
        ("git", "add", "."),
        ("git", "commit", "--quiet", "-m", "fixture"),
    )
    for command in commands:
        subprocess.run(command, cwd=destination, check=True, capture_output=True, text=True)
    return destination


class PackageCliTests(unittest.TestCase):
    def test_help_exposes_bounded_commands_and_explicit_arguments(self) -> None:
        top = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"], check=True, capture_output=True, text=True
        ).stdout
        build = subprocess.run(
            [sys.executable, str(SCRIPT), "build", "--help"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertIn("{build,check}", top)
        self.assertNotIn("publish", top.casefold())
        for option in ("--repo-root", "--profile", "--output", "--frozen"):
            self.assertIn(option, build)


class DistributionTests(unittest.TestCase):
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
        self.source = self.clean_source

    def use_isolated_source(self) -> None:
        self.source = self.root / "source"
        shutil.copytree(self.clean_source, self.source)

    def build(self, name: str = "output") -> Path:
        output = self.root / name
        PACKAGER.build(self.source, output)
        return output

    def test_complete_inventory_and_detached_folder_resources(self) -> None:
        output = self.build()
        inventory = json.loads((output / "release-inventory.json").read_text(encoding="utf-8"))
        manifest = PACKAGER.validate_repository(self.source)
        skills = manifest["skills"]
        expected_full_files = len(PACKAGER.distributed_files(manifest)) + 3
        expected_individual_files = sum(1 + len(entry["resources"]) + 3 for entry in skills)
        self.assertEqual(inventory["profile"], "portable")
        self.assertFalse(inventory["source"]["working_tree_dirty"])
        self.assertEqual(
            len(inventory["files"]), expected_full_files + expected_individual_files
        )
        self.assertEqual(len(inventory["artifacts"]), len(skills) + 1)
        self.assertEqual(set(inventory["packaging_inputs"]), set(PACKAGER.PACKAGING_INPUTS))
        self.assertEqual(len(list((output / "full" / "skills").iterdir())), len(skills))

        detached = self.root / "detached" / "rpacore-project-setup"
        shutil.copytree(output / "individual" / "rpacore-project-setup", detached)
        skill = (detached / "SKILL.md").read_text(encoding="utf-8")
        compatibility = json.loads(
            (detached / "references" / "compatibility.json").read_text(encoding="utf-8")
        )
        self.assertIn("references/compatibility.json", skill)
        self.assertNotIn("../../manifest.toml", skill)
        self.assertEqual(compatibility["core"]["version_spec"], "==0.3.0")
        PACKAGER.check(self.source, output)

    def test_untracked_source_marks_candidate_dirty(self) -> None:
        self.use_isolated_source()
        (self.source / "untracked-note.txt").write_text(
            "not a frozen input\n", encoding="utf-8", newline="\n"
        )
        inventory = PACKAGER.build(self.source, self.root / "dirty")
        self.assertTrue(inventory["source"]["working_tree_dirty"])

        frozen_output = self.root / "frozen-dirty"
        with self.assertRaisesRegex(PACKAGER.ValidationError, "clean Git worktree"):
            PACKAGER.build(self.source, frozen_output, frozen=True)
        self.assertFalse(frozen_output.exists())

    def test_frozen_build_accepts_clean_source(self) -> None:
        output = self.root / "frozen"
        inventory = PACKAGER.build(self.source, output, frozen=True)
        self.assertFalse(inventory["source"]["working_tree_dirty"])
        PACKAGER.check(self.source, output, frozen=True)

    def test_in_tree_output_must_be_explicitly_git_ignored(self) -> None:
        self.use_isolated_source()
        rejected = self.source / "skills" / "staging"
        with self.assertRaisesRegex(PACKAGER.ValidationError, "explicitly Git-ignored"):
            PACKAGER.build(self.source, rejected)
        self.assertFalse(rejected.exists())

        allowed = self.source / "validation-artifacts" / "portable"
        PACKAGER.build(self.source, allowed)
        PACKAGER.check(self.source, allowed)

    def test_rebuild_is_byte_deterministic(self) -> None:
        first = self.build("first")
        second = self.build("second")
        self.assertEqual(PACKAGER._output_files(first), PACKAGER._output_files(second))

    def test_tampered_and_missing_resources_are_rejected_without_repair(self) -> None:
        output = self.build("tampered")
        resource = output / "individual/rpacore-project-setup/references/compatibility.json"
        resource.write_bytes(resource.read_bytes() + b" ")
        tampered = resource.read_bytes()
        with self.assertRaisesRegex(PACKAGER.ValidationError, "content mismatch"):
            PACKAGER.check(self.source, output)
        self.assertEqual(resource.read_bytes(), tampered)

        missing_output = self.build("missing")
        (missing_output / "full/skills/rpacore-project-setup/references/compatibility.json").unlink()
        with self.assertRaisesRegex(PACKAGER.ValidationError, "inventory mismatch"):
            PACKAGER.check(self.source, missing_output)

    def test_source_path_escape_and_allowlist_are_rejected(self) -> None:
        self.use_isolated_source()
        manifest = self.source / "manifest.toml"
        text = manifest.read_text(encoding="utf-8").replace(
            'path = "skills/rpacore-project-setup/references/compatibility.json"',
            'path = "../compatibility.json"',
            1,
        )
        manifest.write_text(text, encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(PACKAGER.ValidationError, "resource path must be"):
            PACKAGER.build(self.source, self.root / "escape")
        self.assertFalse((self.root / "escape").exists())

        manifest.write_bytes((REPO_ROOT / "manifest.toml").read_bytes())
        extra = self.source / "skills/rpacore-project-setup/undeclared.txt"
        extra.write_text("not allowlisted\n", encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(PACKAGER.ValidationError, "extra entries"):
            PACKAGER.build(self.source, self.root / "source-extra")

    def test_output_allowlist_rejects_extra_files(self) -> None:
        output = self.build()
        extra = output / "unexpected.txt"
        extra.write_text("not allowlisted\n", encoding="utf-8", newline="\n")
        with self.assertRaisesRegex(PACKAGER.ValidationError, "inventory mismatch"):
            PACKAGER.check(self.source, output)

    def test_build_handles_spaces_and_unicode_and_cleans_partial_failure(self) -> None:
        output = self.root / "portable output ç"
        PACKAGER.build(self.source, output)
        PACKAGER.check(self.source, output)

        failed = self.root / "failed"
        with patch.object(PACKAGER, "_write_zip", side_effect=OSError("controlled failure")):
            with self.assertRaisesRegex(OSError, "controlled failure"):
                PACKAGER.build(self.source, failed)
        self.assertFalse(failed.exists())


if __name__ == "__main__":
    unittest.main()
