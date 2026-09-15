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
import zipfile

from tests.support import make_git_source


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import package_skills as PACKAGER

SCRIPT = SCRIPTS / "verify_release.py"
SPEC = importlib.util.spec_from_file_location("verify_release", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load release verifier: {SCRIPT}")
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class ReleaseVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source_temporary = tempfile.TemporaryDirectory()
        cls.source = make_git_source(Path(cls.source_temporary.name) / "source")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.source_temporary.cleanup()

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def make_assets(self) -> Path:
        package = self.root / "package"
        PACKAGER.build(self.source, package, frozen=True)
        assets = self.root / "assets"
        assets.mkdir()
        for archive in (package / "archives").iterdir():
            shutil.copy2(archive, assets / archive.name)
        for name in ("release-inventory.json", "release-inventory.sha256"):
            shutil.copy2(package / name, assets / name)
        return assets

    def test_verifies_assets_and_installs_every_skill_from_both_layouts(self) -> None:
        assets = self.make_assets()
        output = self.root / "reconstructed"
        install = self.root / "installed"

        inventory = VERIFIER.verify_release(
            self.source, assets, output, install, frozen=True
        )

        manifest = PACKAGER.validate_repository(self.source)
        names = {entry["name"] for entry in manifest["skills"]}
        self.assertEqual(inventory["source"]["working_tree_dirty"], False)
        self.assertEqual(
            {path.name for path in (install / "full").iterdir()}, names
        )
        self.assertEqual(
            {path.name for path in (install / "individual").iterdir()}, names
        )
        PACKAGER.check(self.source, output, frozen=True)

    def test_extra_asset_is_rejected_before_output(self) -> None:
        assets = self.make_assets()
        (assets / "unexpected.txt").write_text(
            "not allowlisted\n", encoding="utf-8", newline="\n"
        )
        output = self.root / "reconstructed"
        install = self.root / "installed"

        with self.assertRaisesRegex(
            PACKAGER.ValidationError, "release asset allowlist mismatch"
        ):
            VERIFIER.verify_release(self.source, assets, output, install, frozen=True)

        self.assertFalse(output.exists())
        self.assertFalse(install.exists())

    def test_ordinary_failure_removes_only_created_outputs(self) -> None:
        assets = self.make_assets()
        output = self.root / "reconstructed"
        install = self.root / "installed"

        with patch.object(
            VERIFIER, "_rehearse_installs", side_effect=OSError("controlled failure")
        ):
            with self.assertRaisesRegex(OSError, "controlled failure"):
                VERIFIER.verify_release(
                    self.source, assets, output, install, frozen=True
                )

        self.assertTrue(assets.exists())
        self.assertFalse(output.exists())
        self.assertFalse(install.exists())

    def test_symlinked_asset_argument_is_rejected_without_platform_privilege(self) -> None:
        assets = self.make_assets()
        output = self.root / "reconstructed"
        install = self.root / "installed"
        original_is_symlink = Path.is_symlink

        with patch.object(
            Path,
            "is_symlink",
            autospec=True,
            side_effect=lambda path: path == assets or original_is_symlink(path),
        ):
            with self.assertRaisesRegex(
                PACKAGER.ValidationError, "release assets must not be a symlink"
            ):
                VERIFIER.verify_release(
                    self.source, assets, output, install, frozen=True
                )

        self.assertFalse(output.exists())
        self.assertFalse(install.exists())

    def test_archive_escape_is_rejected_before_extraction(self) -> None:
        assets = self.make_assets()
        archive = assets / "rpacore-project-setup.zip"
        with zipfile.ZipFile(archive, "a") as stream:
            stream.writestr("rpacore-project-setup/../escape.txt", b"escape\n")

        inventory_path = assets / "release-inventory.json"
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        inventory["artifacts"]["archives/rpacore-project-setup.zip"] = (
            PACKAGER.sha256_of(archive)
        )
        inventory_path.write_text(
            json.dumps(inventory, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        (assets / "release-inventory.sha256").write_text(
            PACKAGER.inventory_checksum_text(PACKAGER.sha256_of(inventory_path)),
            encoding="utf-8",
            newline="\n",
        )
        output = self.root / "reconstructed"
        install = self.root / "installed"

        with self.assertRaisesRegex(
            PACKAGER.ValidationError, "release archive member allowlist mismatch"
        ):
            VERIFIER.verify_release(self.source, assets, output, install, frozen=True)

        self.assertFalse((self.root / "escape.txt").exists())
        self.assertFalse(output.exists())
        self.assertFalse(install.exists())


class ReleaseVerifierCliTests(unittest.TestCase):
    def test_help_requires_explicit_nonpublishing_paths(self) -> None:
        help_text = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        for option in (
            "--repo-root",
            "--assets",
            "--output",
            "--install-root",
            "--profile",
            "--frozen",
        ):
            self.assertIn(option, help_text)


if __name__ == "__main__":
    unittest.main()
