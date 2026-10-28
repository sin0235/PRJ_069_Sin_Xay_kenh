import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ha_tang.nas_trien_khai_sach.nas_runtime_ops import (
    atomic_copy_file,
    create_manifest,
    validate_owner_password_file,
    verify_backup,
)


class RuntimeOpsTests(unittest.TestCase):
    def test_owner_password_must_be_one_utf8_line_with_valid_length(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "owner-password"
            path.write_bytes("correct horse battery staple\n".encode("utf-8"))
            validate_owner_password_file(path)
            path.write_bytes(b"short\n")
            with self.assertRaises(ValueError):
                validate_owner_password_file(path)
            path.write_bytes(b"long-enough-password\nsecond-line\n")
            with self.assertRaises(ValueError):
                validate_owner_password_file(path)
            path.write_bytes(b"\xff")
            with self.assertRaises(ValueError):
                validate_owner_password_file(path)

    def test_atomic_secret_copy_is_private_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            destination = Path(directory) / "backup" / "secret"
            source.write_bytes(b"opaque secret")
            atomic_copy_file(source, destination)
            self.assertEqual(destination.read_bytes(), b"opaque secret")
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                atomic_copy_file(source, destination)

    def test_backup_manifest_verifies_checksums_and_detects_damage(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory)
            (backup / "data.tar").write_bytes(b"isolated database archive")
            secrets = backup / "secrets"
            secrets.mkdir()
            (secrets / "owner-password").write_bytes(b"private")
            manifest = create_manifest(backup, {"project": "contract-test"})
            self.assertEqual(manifest["version"], 1)
            self.assertEqual(verify_backup(backup)["metadata"]["project"], "contract-test")
            (backup / "data.tar").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                verify_backup(backup)


if __name__ == "__main__":
    unittest.main()
