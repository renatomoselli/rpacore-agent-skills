from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tests.support import make_git_source


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "package_skills.py"
SPEC = importlib.util.spec_from_file_location("package_skills", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load packager: {SCRIPT}")
PACKAGER = importlib.util.module_from_spec(SPEC)
sys.path.insert(0, str(REPO_ROOT / "scripts"))
SPEC.loader.exec_module(PACKAGER)

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
        self.assertIn("{build,check,compare}", top)
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
            inventory["companion"],
            {
                "version": manifest["companion_version"],
                "status": manifest["status"],
                "license": manifest["license"],
            },
        )
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

    def test_frozen_build_rejects_staged_modification(self) -> None:
        self.use_isolated_source()
        readme = self.source / "README.md"
        readme.write_bytes(readme.read_bytes() + b"\nStaged release probe.\n")
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=self.source,
            check=True,
            capture_output=True,
            text=True,
        )

        output = self.root / "frozen-staged"
        with self.assertRaisesRegex(PACKAGER.ValidationError, "clean Git worktree"):
            PACKAGER.build(self.source, output, frozen=True)
        self.assertFalse(output.exists())

    def test_ignored_interrupted_transaction_temp_does_not_poison_frozen_build(self) -> None:
        self.use_isolated_source()
        orphan = self.source / ".skills-write-interrupted.tmp"
        orphan.write_bytes(b"incomplete generated content\n")

        output = self.root / "frozen-after-interruption"
        inventory = PACKAGER.build(self.source, output, frozen=True)

        self.assertFalse(inventory["source"]["working_tree_dirty"])
        self.assertNotIn(orphan.name, PACKAGER._output_files(output))
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

    def test_archives_use_platform_independent_stored_members(self) -> None:
        output = self.build()
        for path in (output / "archives").iterdir():
            with self.subTest(archive=path.name), zipfile.ZipFile(path) as archive:
                members = archive.infolist()
                self.assertTrue(members)
                self.assertEqual(
                    {member.compress_type for member in members},
                    {zipfile.ZIP_STORED},
                )

    def test_cross_platform_candidates_compare_equal(self) -> None:
        first = self.build("first")
        second = self.build("second")
        hashes = PACKAGER.compare(self.source, first, second)
        self.assertEqual(len(hashes), len(PACKAGER.release_asset_paths(
            PACKAGER.validate_repository(self.source)
        )))
        self.assertEqual(
            set(hashes),
            {
                "archives/rpacore-agent-skills-portable.zip",
                "release-inventory.json",
                "release-inventory.sha256",
            } | {
                f"archives/{entry['name']}.zip"
                for entry in PACKAGER.validate_repository(self.source)["skills"]
            },
        )

    def test_tampered_archive_fails_compare_naming_the_file(self) -> None:
        first = self.build("first")
        second = self.build("second")
        archive = second / "archives/rpacore-project-setup.zip"
        archive.write_bytes(archive.read_bytes() + b" ")
        with self.assertRaisesRegex(
            PACKAGER.ValidationError,
            "release asset hash mismatch.*rpacore-project-setup\\.zip",
        ):
            PACKAGER.compare(self.source, first, second)

    def test_missing_asset_fails_compare(self) -> None:
        first = self.build("first")
        second = self.build("second")
        (second / "release-inventory.sha256").unlink()
        with self.assertRaisesRegex(
            PACKAGER.ValidationError, "missing release-inventory\\.sha256"
        ):
            PACKAGER.compare(self.source, first, second)

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

    def test_tampered_inventory_and_checksum_are_rejected_without_repair(self) -> None:
        for name, relative in (
            ("inventory", "release-inventory.json"),
            ("checksum", "release-inventory.sha256"),
        ):
            with self.subTest(name=name):
                output = self.build(f"tampered-{name}")
                path = output / relative
                path.write_bytes(path.read_bytes() + b"tampered\n")
                tampered = path.read_bytes()
                with self.assertRaisesRegex(PACKAGER.ValidationError, "content mismatch"):
                    PACKAGER.check(self.source, output)
                self.assertEqual(path.read_bytes(), tampered)

        coordinated = self.build("tampered-inventory-and-checksum")
        inventory_path = coordinated / "release-inventory.json"
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        inventory["profile"] = "tampered"
        inventory_path.write_text(
            json.dumps(inventory, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        checksum_path = coordinated / "release-inventory.sha256"
        checksum_path.write_text(
            PACKAGER.inventory_checksum_text(PACKAGER.sha256_of(inventory_path)),
            encoding="utf-8",
            newline="\n",
        )
        with self.assertRaisesRegex(PACKAGER.ValidationError, "content mismatch"):
            PACKAGER.check(self.source, coordinated)

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


class ArchiveSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "zip-source"
        (self.source / "nested").mkdir(parents=True)
        (self.source / "nested/payload.txt").write_text(
            "payload\n", encoding="utf-8", newline="\n"
        )

    def test_file_hashes_returns_relative_identities(self) -> None:
        self.assertEqual(
            PACKAGER.file_hashes(self.source),
            {
                "nested/payload.txt": hashlib.sha256(b"payload\n").hexdigest(),
            },
        )

    def test_zip_members_use_platform_independent_string_order(self) -> None:
        (self.source / "SKILL.md").write_text(
            "instructions\n", encoding="utf-8", newline="\n"
        )
        references = self.source / "references"
        references.mkdir()
        (references / "compatibility.json").write_text(
            "{}\n", encoding="utf-8", newline="\n"
        )
        destination = self.root / "archives" / "ordered.zip"

        PACKAGER._write_zip(self.source, destination, "skill")

        with zipfile.ZipFile(destination) as archive:
            names = archive.namelist()
        self.assertEqual(names, sorted(names))

    def test_file_hashes_rejects_mocked_symlink_without_privilege(self) -> None:
        payload = self.source / "nested/payload.txt"
        with patch.object(
            type(payload),
            "is_symlink",
            autospec=True,
            side_effect=lambda path: path == payload,
        ):
            with self.assertRaisesRegex(
                PACKAGER.ValidationError, "must not contain symlinks"
            ):
                PACKAGER.file_hashes(self.source)

    def test_walk_and_zip_reject_directory_symlink_when_supported(self) -> None:
        link = self.source / "linked-directory"
        try:
            link.symlink_to(self.source / "nested", target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlinks unavailable: {exc}")

        with self.assertRaisesRegex(PACKAGER.ValidationError, "must not contain symlinks"):
            PACKAGER.file_hashes(self.source)
        destination = self.root / "archives" / "unsafe.zip"
        with self.assertRaisesRegex(PACKAGER.ValidationError, "must not contain symlinks"):
            PACKAGER._write_zip(self.source, destination, "unsafe")
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
