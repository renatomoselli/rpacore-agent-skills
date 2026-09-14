from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import tomllib
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from file_transaction import TEMP_PREFIX, replace_files
import validate_skills as validator
import verify_consumer as consumer


def tree_state(root: Path) -> dict[str, tuple[object, ...]]:
    state: dict[str, tuple[object, ...]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            state[relative] = ("directory",)
        elif path.is_file():
            state[relative] = (
                "file",
                path.read_bytes(),
                stat.S_IMODE(path.stat().st_mode),
            )
    return state


class HashMaintenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = SCRIPTS.parent
        shutil.copy2(source / "manifest.toml", self.root / "manifest.toml")
        shutil.copytree(source / "skills", self.root / "skills")
        self.skill = self.root / "skills/rpacore-project-setup/SKILL.md"

    def assert_tree_unchanged(self, before: dict[str, tuple[object, ...]]) -> None:
        self.assertEqual(tree_state(self.root), before)

    def assert_no_transaction_temps(self) -> None:
        self.assertFalse(list(self.root.glob(f"{TEMP_PREFIX}*.tmp")))

    def test_regeneration_changes_only_hashes_and_is_idempotent(self) -> None:
        path = self.root / "manifest.toml"
        before = path.read_bytes()
        with self.skill.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("\nAdditional reviewed setup guidance.\n")
        with self.assertRaisesRegex(validator.ValidationError, "SHA-256 mismatch"):
            validator.validate_repository(self.root)
        manifest = validator.validate_repository(self.root, write_hashes=True)
        after = path.read_bytes()
        self.assertEqual(manifest, tomllib.loads(after.decode("utf-8")))
        strip_hashes = lambda data: re.sub(rb'sha256 = "[0-9a-f]{64}"', b'sha256 = "<hash>"', data)
        self.assertEqual(strip_hashes(before), strip_hashes(after))
        self.assertNotEqual(before, after)
        validator.validate_repository(self.root)
        validator.validate_repository(self.root, write_hashes=True)
        self.assertEqual(path.read_bytes(), after)

    def test_regeneration_rejects_invalid_skill_without_manifest_write(self) -> None:
        path = self.root / "manifest.toml"
        before = path.read_bytes()
        self.skill.write_bytes(self.skill.read_bytes() + b"Read .internal guidance.\n")
        with self.assertRaisesRegex(validator.ValidationError, "forbidden content"):
            validator.validate_repository(self.root, write_hashes=True)
        self.assertEqual(path.read_bytes(), before)
        self.assert_no_transaction_temps()

    def test_regeneration_rejects_crlf_without_normalizing_source(self) -> None:
        before = (self.root / "manifest.toml").read_bytes()
        body = self.skill.read_bytes().replace(b"\n", b"\r\n")
        self.skill.write_bytes(body)
        with self.assertRaisesRegex(validator.ValidationError, "CR/CRLF"):
            validator.validate_repository(self.root, write_hashes=True)
        self.assertEqual((self.root / "manifest.toml").read_bytes(), before)
        self.assertEqual(self.skill.read_bytes(), body)

    def test_core_release_fact_is_independent_of_companion_status(self) -> None:
        manifest = tomllib.loads((self.root / "manifest.toml").read_text(encoding="utf-8"))
        for published in (True, False):
            manifest["core"]["published_release"] = published
            validator._validate_manifest_header(manifest)
        manifest["core"]["published_release"] = "true"
        with self.assertRaisesRegex(validator.ValidationError, "boolean"):
            validator._validate_manifest_header(manifest)

    def test_public_validation_returns_the_checked_manifest(self) -> None:
        manifest = validator.validate_repository(str(self.root))
        self.assertEqual(manifest["core"]["version_spec"], "==0.3.0")
        self.assertEqual(manifest, tomllib.loads((self.root / "manifest.toml").read_text(encoding="utf-8")))

    def test_noncanonical_hash_layout_is_rejected_without_rewriting_toml(self) -> None:
        path = self.root / "manifest.toml"
        original = path.read_bytes().replace(b'sha256 = ', b'sha256\t= ')
        path.write_bytes(original)
        validator.validate_repository(self.root)  # Valid TOML is still readable.
        with self.assertRaisesRegex(validator.ValidationError, "canonical sha256"):
            validator.validate_repository(self.root, write_hashes=True)
        self.assertEqual(path.read_bytes(), original)
        self.assert_no_transaction_temps()

    def test_apply_failure_restores_tree_and_cleans_temporary(self) -> None:
        manifest_path = self.root / "manifest.toml"
        blocker = self.root / "blocked-parent"
        blocker.write_text("not a directory\n", encoding="utf-8", newline="\n")
        before = tree_state(self.root)
        pending = {
            manifest_path: manifest_path.read_bytes() + b"\n",
            blocker / "child": b"cannot be written\n",
        }

        with self.assertRaises(OSError):
            replace_files(self.root, pending, lambda: None)

        self.assert_tree_unchanged(before)
        self.assert_no_transaction_temps()

    def test_transaction_accepts_equivalent_windows_short_path(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows short-path alias test")
        import ctypes

        target = self.root / "manifest.toml"
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetShortPathNameW(
            str(self.root), buffer, len(buffer)
        )
        if not length or length >= len(buffer):
            self.skipTest("Windows short paths unavailable")
        short_root = Path(buffer.value)
        if str(short_root).casefold() == str(self.root).casefold():
            self.skipTest("temporary directory has no distinct short-path alias")

        replace_files(
            self.root,
            {short_root / target.name: b"short-path update\n"},
            lambda: None,
        )

        self.assertEqual(target.read_bytes(), b"short-path update\n")
        self.assert_no_transaction_temps()

    def test_validation_failure_restores_tree_and_cleans_temporary(self) -> None:
        manifest_path = self.root / "manifest.toml"
        resource = self.root / "skills/rpacore-project-setup/references/compatibility.json"
        before = tree_state(self.root)
        pending = {
            manifest_path: manifest_path.read_bytes() + b"\n",
            resource: b"{}\n",
        }

        def reject() -> None:
            raise RuntimeError("controlled validation failure")

        with self.assertRaisesRegex(RuntimeError, "controlled validation failure"):
            replace_files(self.root, pending, reject)

        self.assert_tree_unchanged(before)
        self.assert_no_transaction_temps()

    def test_base_exception_rolls_back_generated_resources(self) -> None:
        class ControlledAbort(BaseException):
            pass

        resource = self.root / "skills/rpacore-project-setup/references/compatibility.json"
        before = tree_state(self.root)

        def abort() -> None:
            raise ControlledAbort()

        with self.assertRaises(ControlledAbort):
            replace_files(self.root, {resource: b"{}\n"}, abort)

        self.assert_tree_unchanged(before)
        self.assert_no_transaction_temps()

    def test_regeneration_preserves_existing_file_mode(self) -> None:
        manifest_path = self.root / "manifest.toml"
        original_mode = stat.S_IMODE(manifest_path.stat().st_mode)
        self.skill.write_bytes(self.skill.read_bytes() + b"\nMode preservation probe.\n")

        validator.validate_repository(self.root, write_hashes=True)

        self.assertEqual(stat.S_IMODE(manifest_path.stat().st_mode), original_mode)

    def test_final_revalidation_failure_rolls_back_all_generated_files(self) -> None:
        resource = self.root / "skills/rpacore-project-setup/references/compatibility.json"
        before = tree_state(self.root)

        with self.assertRaisesRegex(validator.ValidationError, "generated compatibility"):
            replace_files(
                self.root,
                {resource: b"{}\n"},
                lambda: validator.validate_repository(self.root),
            )

        self.assert_tree_unchanged(before)
        self.assert_no_transaction_temps()

    def test_hash_regeneration_is_keyed_by_declared_path(self) -> None:
        manifest_path = self.root / "manifest.toml"
        text = manifest_path.read_text(encoding="utf-8")
        skill_path = "skills/rpacore-project-setup/SKILL.md"
        resource_path = "skills/rpacore-project-setup/references/compatibility.json"
        resource = self.root.joinpath(*resource_path.split("/"))
        manifest = tomllib.loads(text)
        entry = next(item for item in manifest["skills"] if item["path"] == skill_path)
        text = text.replace(
            f'path = "{skill_path}"\nsha256 = "{entry["sha256"]}"',
            f'sha256 = "{entry["sha256"]}"\npath = "{skill_path}"',
            1,
        ).replace(
            f'path = "{resource_path}"\nsha256 = "{entry["resources"][0]["sha256"]}"',
            f'sha256 = "{entry["resources"][0]["sha256"]}"\npath = "{resource_path}"',
            1,
        )
        manifest_path.write_text(text, encoding="utf-8", newline="\n")
        self.skill.write_bytes(self.skill.read_bytes() + b"\nPath-keyed hash probe.\n")

        updated = validator.validate_repository(self.root, write_hashes=True)
        updated_entry = next(item for item in updated["skills"] if item["path"] == skill_path)
        self.assertEqual(
            updated_entry["sha256"], hashlib.sha256(self.skill.read_bytes()).hexdigest()
        )
        self.assertEqual(
            updated_entry["resources"][0]["sha256"], hashlib.sha256(resource.read_bytes()).hexdigest()
        )
        validator.validate_repository(self.root)



class WheelSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        import subprocess
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.core = self.root / "core"
        (self.core / "rpacore").mkdir(parents=True)
        self.source = {"rpacore/__init__.py": b"from .step import Step\n",
                       "rpacore/step.py": b"class Step:\n    pass\n"}
        for name, payload in self.source.items():
            (self.core / name).write_bytes(payload)
        for args in (["init", "--quiet"], ["config", "user.email", "test@example.invalid"],
                     ["config", "user.name", "Test"], ["-c", "core.autocrlf=false", "add", "rpacore"],
                     ["commit", "--quiet", "-m", "baseline"]):
            subprocess.run(["git", *args], cwd=self.core, capture_output=True, check=True)
        self.commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.core,
                                     capture_output=True, text=True, check=True).stdout.strip()

    def wheel(self, payloads: dict[str, bytes]) -> Path:
        import zipfile
        path = self.root / "consumer.whl"
        with zipfile.ZipFile(path, "w") as archive:
            for name, payload in payloads.items():
                archive.writestr(name, payload)
            archive.writestr("rpacore-0.3.0.dist-info/METADATA", "Name: rpacore\nVersion: 0.3.0\n")
        return path

    def test_crlf_source_preserves_raw_wheel_identity(self) -> None:
        payloads = {name: data.replace(b"\n", b"\r\n") for name, data in self.source.items()}
        hashes = consumer.wheel_contract(self.wheel(payloads), self.core, self.commit, "0.3.0")
        self.assertEqual(hashes["rpacore/step.py"], hashlib.sha256(payloads["rpacore/step.py"]).hexdigest())

    def test_same_version_does_not_hide_stale_or_changed_code(self) -> None:
        changed = dict(self.source)
        changed["rpacore/step.py"] = b"class Step:\n    changed = True\n"
        with self.assertRaisesRegex(validator.ValidationError, "source differs"):
            consumer.wheel_contract(self.wheel(changed), self.core, self.commit, "0.3.0")
        obsolete = dict(self.source)
        obsolete["rpacore/skill.py"] = obsolete.pop("rpacore/step.py")
        with self.assertRaisesRegex(validator.ValidationError, "package files differ"):
            consumer.wheel_contract(self.wheel(obsolete), self.core, self.commit, "0.3.0")


if __name__ == "__main__":
    unittest.main()
