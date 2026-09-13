from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_skills.py"
SPEC = importlib.util.spec_from_file_location("validate_skills", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Could not load validator: {SCRIPT_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temporary_directory.name) / "companion"
        self.repo_root.mkdir()
        shutil.copy2(REPO_ROOT / "manifest.toml", self.repo_root / "manifest.toml")
        shutil.copytree(REPO_ROOT / "skills", self.repo_root / "skills")

    @property
    def setup_skill(self) -> Path:
        return self.repo_root / "skills" / "rpacore-project-setup" / "SKILL.md"

    def initialize_core_repository(self) -> tuple[Path, str]:
        core_repo = Path(self.temporary_directory.name) / "core"
        docs = core_repo / "docs"
        docs.mkdir(parents=True)
        (docs / "api.md").write_text("# API\n", encoding="utf-8", newline="\n")
        commands = (
            ("git", "init", "--quiet"),
            ("git", "config", "user.email", "validator@example.invalid"),
            ("git", "config", "user.name", "Validator Test"),
            ("git", "add", "docs/api.md"),
            ("git", "commit", "--quiet", "-m", "baseline"),
        )
        for command in commands:
            subprocess.run(command, cwd=core_repo, check=True, capture_output=True, text=True)
        commit = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=core_repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return core_repo, commit

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_repository_contract_passes(self) -> None:
        VALIDATOR.validate_repository(REPO_ROOT)

    def test_manifest_lists_the_seven_public_skills(self) -> None:
        manifest = tomllib.loads((REPO_ROOT / "manifest.toml").read_text(encoding="utf-8"))
        names = {entry["name"] for entry in manifest["skills"]}

        self.assertEqual(
            names,
            {
                "rpacore-automation-development",
                "rpacore-diagnostics-inspection",
                "rpacore-durability-recovery",
                "rpacore-project-setup",
                "rpacore-queue-processing",
                "rpacore-reporting-notifications",
                "rpacore-testing-review",
            },
        )

    def test_changed_skill_body_fails_hash_verification(self) -> None:
        skill = self.repo_root / "skills" / "rpacore-project-setup" / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8") + "Changed.\n",
            encoding="utf-8",
            newline="\n",
        )

        with self.assertRaisesRegex(VALIDATOR.ValidationError, "SHA-256 mismatch"):
            VALIDATOR.validate_repository(self.repo_root)

    def test_write_regeneration_round_trip_updates_only_hashes(self) -> None:
        skill = self.repo_root / "skills" / "rpacore-project-setup" / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8") + "\nRegeneration probe.\n",
            encoding="utf-8",
            newline="\n",
        )
        with self.assertRaisesRegex(VALIDATOR.ValidationError, "SHA-256 mismatch"):
            VALIDATOR.validate_repository(self.repo_root)

        before = (self.repo_root / "manifest.toml").read_text(encoding="utf-8").splitlines()
        VALIDATOR.validate_repository(self.repo_root, write_hashes=True)
        VALIDATOR.validate_repository(self.repo_root)
        after = (self.repo_root / "manifest.toml").read_text(encoding="utf-8").splitlines()

        self.assertEqual(
            [line for line in before if "sha256" not in line],
            [line for line in after if "sha256" not in line],
        )
        changed = [(old, new) for old, new in zip(before, after) if old != new]
        self.assertEqual(len(changed), 1)
        self.assertTrue(all("sha256" in old for old, _ in changed))

    def test_unexpected_frontmatter_field_is_rejected(self) -> None:
        skill = self.repo_root / "skills" / "rpacore-project-setup" / "SKILL.md"
        text = skill.read_text(encoding="utf-8").replace(
            "description:", "license: Apache-2.0\ndescription:", 1
        )
        skill.write_text(text, encoding="utf-8", newline="\n")

        with self.assertRaisesRegex(VALIDATOR.ValidationError, "frontmatter fields"):
            VALIDATOR.validate_repository(self.repo_root)

    def test_private_planning_reference_is_rejected(self) -> None:
        skill = self.repo_root / "skills" / "rpacore-project-setup" / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8") + "Read .internal before work.\n",
            encoding="utf-8",
            newline="\n",
        )

        with self.assertRaisesRegex(VALIDATOR.ValidationError, "forbidden content"):
            VALIDATOR.validate_repository(self.repo_root)

    def test_mutable_main_documentation_link_is_rejected(self) -> None:
        skill = self.repo_root / "skills" / "rpacore-project-setup" / "SKILL.md"
        text = skill.read_text(encoding="utf-8").replace(
            "blob/493252649ee6b9d387008e6b7ed41908e2733f46/",
            "blob/main/",
            1,
        )
        skill.write_text(text, encoding="utf-8", newline="\n")

        with self.assertRaisesRegex(VALIDATOR.ValidationError, "forbidden content"):
            VALIDATOR.validate_repository(self.repo_root)

    def test_extra_executable_file_is_rejected(self) -> None:
        script = self.repo_root / "skills" / "rpacore-project-setup" / "run.py"
        script.write_text("print('unexpected')\n", encoding="utf-8", newline="\n")

        with self.assertRaisesRegex(VALIDATOR.ValidationError, "contains extra entries"):
            VALIDATOR.validate_repository(self.repo_root)

    def test_unsafe_manifest_path_is_rejected(self) -> None:
        manifest = self.repo_root / "manifest.toml"
        text = manifest.read_text(encoding="utf-8").replace(
            'path = "skills/rpacore-automation-development/SKILL.md"',
            'path = "../outside/SKILL.md"',
            1,
        )
        manifest.write_text(text, encoding="utf-8", newline="\n")

        with self.assertRaisesRegex(VALIDATOR.ValidationError, "path must be"):
            VALIDATOR.validate_repository(self.repo_root)

    def test_missing_skill_directory_is_bounded(self) -> None:
        shutil.rmtree(self.repo_root / "skills")

        with self.assertRaisesRegex(VALIDATOR.ValidationError, "skill directory is missing"):
            VALIDATOR.validate_repository(self.repo_root)

    def test_unknown_manifest_field_is_rejected(self) -> None:
        manifest = self.repo_root / "manifest.toml"
        text = manifest.read_text(encoding="utf-8").replace(
            "schema_version = 1\n",
            "schema_version = 1\nunexpected = true\n",
            1,
        )
        manifest.write_text(text, encoding="utf-8", newline="\n")

        with self.assertRaisesRegex(VALIDATOR.ValidationError, "fields must be exactly"):
            VALIDATOR.validate_repository(self.repo_root)

    def test_text_contract_rejects_malformed_encodings_and_endings(self) -> None:
        cases = (
            ("bom", b"\xef\xbb\xbftext\n", "UTF-8 BOM is not allowed"),
            ("crlf", b"text\r\n", "CR/CRLF line endings are not allowed"),
            ("invalid-utf8", b"\xff\n", "expected UTF-8 text"),
            ("missing-newline", b"text", "final newline is required"),
        )
        for name, payload, expected in cases:
            with self.subTest(name=name):
                path = self.repo_root / f"{name}.txt"
                path.write_bytes(payload)
                with self.assertRaisesRegex(VALIDATOR.ValidationError, expected):
                    VALIDATOR._read_utf8_lf(path)

    def test_manifest_identity_invariants_fail_closed(self) -> None:
        cases = (
            ("schema_version = 1", "schema_version = 2", "schema_version must be 1"),
            (
                'companion_version = "0.1.0-dev.0"',
                'companion_version = "not-a-version"',
                "invalid companion_version",
            ),
            (
                'status = "development-only"',
                'status = "released"',
                "must remain development-only",
            ),
            ('license = "Apache-2.0"', 'license = "MIT"', "license must be Apache-2.0"),
            (
                'validation_python = ">=3.11"',
                'validation_python = ">=3.12"',
                "validation_python must be >=3.11",
            ),
            (
                'commit = "493252649ee6b9d387008e6b7ed41908e2733f46"',
                'commit = "not-a-commit"',
                "commit must be 40 lowercase hexadecimal",
            ),
            (
                "blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs",
                "blob/main/docs",
                "docs_base must equal immutable baseline",
            ),
            ('published_release = true', 'published_release = "yes"', "must be a boolean"),
            ('version_spec = "==0.3.0"', 'version_spec = ">=0.3.0"', "one exact tested release"),
        )
        for old, new, expected in cases:
            with self.subTest(replacement=new):
                with tempfile.TemporaryDirectory() as directory:
                    case_root = Path(directory) / "companion"
                    shutil.copytree(self.repo_root, case_root)
                    manifest = case_root / "manifest.toml"
                    text = manifest.read_text(encoding="utf-8")
                    self.assertIn(old, text)
                    manifest.write_text(
                        text.replace(old, new, 1), encoding="utf-8", newline="\n"
                    )
                    with self.assertRaisesRegex(VALIDATOR.ValidationError, expected):
                        VALIDATOR.validate_repository(case_root)

    def test_skill_limits_and_case_insensitive_leakage_fail_closed(self) -> None:
        cases = (
            ("bytes", b"x" * VALIDATOR.MAX_SKILL_BYTES, "exceeds 12000 bytes"),
            ("lines", b"\n" * VALIDATOR.MAX_SKILL_LINES, "exceeds 120 lines"),
            ("case-folded-private-path", b"Read D:\\REPOS before work.\n", "forbidden content"),
        )
        for name, suffix, expected in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as directory:
                    case_root = Path(directory) / "companion"
                    shutil.copytree(self.repo_root, case_root)
                    skill = case_root / "skills" / "rpacore-project-setup" / "SKILL.md"
                    skill.write_bytes(skill.read_bytes() + suffix)
                    with self.assertRaisesRegex(VALIDATOR.ValidationError, expected):
                        VALIDATOR.validate_repository(case_root)

    def test_skill_metadata_and_routing_guards_fail_closed(self) -> None:
        cases = (
            (
                "frontmatter-name",
                "name: rpacore-project-setup",
                "name: wrong-name",
                "frontmatter name does not match",
            ),
            (
                "compatibility-route",
                "rpacore version",
                "the installed version",
                "body must route compatibility",
            ),
            (
                "manifest-route",
                "manifest.toml",
                "compatibility manifest",
                "body must route compatibility",
            ),
            (
                "outside-baseline",
                "https://github.com/renatomoselli/rpacore/blob/493252649ee6b9d387008e6b7ed41908e2733f46/docs/tutorial.md",
                "https://example.invalid/docs/tutorial.md",
                "absolute link is outside manifest baseline",
            ),
        )
        for name, old, new, expected in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as directory:
                    case_root = Path(directory) / "companion"
                    shutil.copytree(self.repo_root, case_root)
                    skill = case_root / "skills" / "rpacore-project-setup" / "SKILL.md"
                    text = skill.read_text(encoding="utf-8")
                    self.assertIn(old, text)
                    replace_all = {"compatibility-route", "manifest-route"}
                    replacement_count = -1 if name in replace_all else 1
                    skill.write_text(
                        text.replace(old, new, replacement_count),
                        encoding="utf-8",
                        newline="\n",
                    )
                    with self.assertRaisesRegex(VALIDATOR.ValidationError, expected):
                        VALIDATOR.validate_repository(case_root)

    def test_skill_entry_invariants_fail_closed(self) -> None:
        manifest = tomllib.loads((self.repo_root / "manifest.toml").read_text(encoding="utf-8"))
        core = manifest["core"]
        original = manifest["skills"][0]
        cases = (
            ("name", "Invalid_Name", "invalid skill name"),
            ("path", "skills/wrong/SKILL.md", "path must be"),
            ("sha256", "NOT-A-SHA256", "sha256 must be 64 lowercase hex"),
        )
        for field, value, expected in cases:
            with self.subTest(field=field):
                entry = dict(original)
                entry[field] = value
                with self.assertRaisesRegex(VALIDATOR.ValidationError, expected):
                    VALIDATOR._validate_skill(
                        repo_root=self.repo_root,
                        entry=entry,
                        docs_base=core["docs_base"],
                    )

    def test_skill_description_and_document_links_fail_closed(self) -> None:
        cases = (
            ("long-description", "description exceeds 1024 characters"),
            ("missing-document-link", "at least one immutable Core documentation link"),
            ("unsafe-document-link", "unsafe documentation path"),
        )
        for name, expected in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as directory:
                    case_root = Path(directory) / "companion"
                    shutil.copytree(self.repo_root, case_root)
                    skill = case_root / "skills" / "rpacore-project-setup" / "SKILL.md"
                    text = skill.read_text(encoding="utf-8")
                    if name == "long-description":
                        lines = text.splitlines()
                        description_index = next(
                            index for index, line in enumerate(lines) if line.startswith("description: ")
                        )
                        lines[description_index] = f"description: {'x' * 1025}"
                        text = "\n".join(lines) + "\n"
                    elif name == "missing-document-link":
                        text = text.replace("https://", "relative://")
                    else:
                        text = text.replace("/docs/tutorial.md", "/docs/../tutorial.md", 1)
                    skill.write_text(text, encoding="utf-8", newline="\n")
                    with self.assertRaisesRegex(VALIDATOR.ValidationError, expected):
                        VALIDATOR.validate_repository(case_root)

    def test_manifest_skill_order_and_uniqueness_are_enforced(self) -> None:
        cases = (
            (
                'name = "rpacore-automation-development"',
                'name = "rpacore-z-automation-development"',
                "skills must be sorted by name",
            ),
            (
                'name = "rpacore-diagnostics-inspection"',
                'name = "rpacore-automation-development"',
                "skill names must be unique",
            ),
        )
        for old, new, expected in cases:
            with self.subTest(expected=expected):
                with tempfile.TemporaryDirectory() as directory:
                    case_root = Path(directory) / "companion"
                    shutil.copytree(self.repo_root, case_root)
                    manifest = case_root / "manifest.toml"
                    text = manifest.read_text(encoding="utf-8")
                    manifest.write_text(
                        text.replace(old, new, 1), encoding="utf-8", newline="\n"
                    )
                    with self.assertRaisesRegex(VALIDATOR.ValidationError, expected):
                        VALIDATOR.validate_repository(case_root)

    def test_core_checkout_identity_and_document_targets_are_enforced(self) -> None:
        core_repo, commit = self.initialize_core_repository()
        docs_base = "https://example.invalid/rpacore/blob/baseline/docs"
        core = {"commit": commit, "docs_base": docs_base}
        api_link = f"{docs_base}/api.md"

        VALIDATOR._validate_core_checkout(core_repo, core, {api_link})

        with self.assertRaisesRegex(VALIDATOR.ValidationError, "commit mismatch"):
            VALIDATOR._validate_core_checkout(
                core_repo, {"commit": "0" * 40, "docs_base": docs_base}, {api_link}
            )
        with self.assertRaisesRegex(VALIDATOR.ValidationError, "target is missing"):
            VALIDATOR._validate_core_checkout(
                core_repo, core, {f"{docs_base}/missing.md"}
            )

    def test_symlinked_skill_is_rejected_when_supported(self) -> None:
        skill = self.setup_skill
        real_skill = skill.with_name("REAL_SKILL.md")
        skill.rename(real_skill)
        try:
            skill.symlink_to(real_skill.name)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")

        with self.assertRaisesRegex(VALIDATOR.ValidationError, "must not use symlinks"):
            VALIDATOR.validate_repository(self.repo_root)


if __name__ == "__main__":
    unittest.main()
