import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import urllib.request
from unittest.mock import patch

from acbr_printer import ErroAcbrImpressora
from acbr_printer import installer


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="acbr-printer-install-test-")
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, special=None):
        path = self.root / "fixture.tgz"
        worker = b"native fixture not executable"
        manifest = {"formatVersion": 1, "sourceRevision": 48590, "platform": sys.platform,
                    "arch": "x64", "executable": "worker", "files": {"worker": hashlib.sha256(worker).hexdigest()}}
        prefix = f"package/runtime/{sys.platform}-x64/"
        with tarfile.open(path, "w:gz") as out:
            for name, data in [(prefix + "worker", worker), (prefix + "manifest.json", json.dumps(manifest).encode())]:
                member = tarfile.TarInfo(name)
                member.size = len(data)
                out.addfile(member, io.BytesIO(data))
            if special:
                out.addfile(*special)
        return path

    def approved(self, archive):
        return patch.multiple(installer, APPROVED_SHA256=hashlib.sha256(archive.read_bytes()).hexdigest(), APPROVED_BYTES=archive.stat().st_size)

    def test_offline_archive_is_verified_and_installed_atomically(self):
        archive = self.archive()
        destination = self.root / "installed"
        with self.approved(archive), patch.object(urllib.request, "urlopen", side_effect=AssertionError("Network not allowed")):
            result = installer.instalar_runtime(archive, destination)
        self.assertEqual(result["runtimeDirectory"], str(destination))
        self.assertFalse(result["downloadExecutado"])
        self.assertTrue((destination / "manifest.json").is_file())
        self.assertFalse(list(self.root.glob(".acbr-printer-install-*")))

    def test_remote_install_is_disabled_for_unpublished_runtime(self):
        destination = self.root / "not-created"
        with patch.object(urllib.request, "urlopen", side_effect=AssertionError("Network not allowed")), self.assertRaises(ErroAcbrImpressora) as raised:
            installer.instalar_runtime(destino=destination)
        self.assertEqual(raised.exception.codigo, "RUNTIME_LOCAL_NAO_PUBLICADO")
        self.assertFalse(destination.exists())

    def test_wrong_archive_hash_never_creates_destination(self):
        archive = self.archive()
        destination = self.root / "installed"
        with self.assertRaises(ErroAcbrImpressora) as raised:
            installer.instalar_runtime(archive, destination)
        self.assertEqual(raised.exception.codigo, "ARTEFATO_DIVERGENTE")
        self.assertFalse(destination.exists())
        self.assertFalse(list(self.root.glob(".acbr-printer-install-*")))

    def test_existing_destination_is_never_replaced(self):
        destination = self.root / "existing"
        destination.mkdir()
        sentinel = destination / "keep"
        sentinel.write_text("original")
        with self.assertRaises(ErroAcbrImpressora) as raised:
            installer.instalar_runtime(self.root / "not read", destination)
        self.assertEqual(raised.exception.codigo, "DESTINO_EXISTENTE")
        self.assertEqual(sentinel.read_text(), "original")

    def test_traversal_and_symlink_archive_members_are_rejected(self):
        for kind in ("traversal", "symlink"):
            with self.subTest(kind=kind):
                member = tarfile.TarInfo("package/../../escape" if kind == "traversal" else "package/link")
                if kind == "symlink":
                    member.type = tarfile.SYMTYPE
                    member.linkname = "../../escape"
                    special = (member,)
                else:
                    member.size = 1
                    special = (member, io.BytesIO(b"x"))
                archive = self.archive(special)
                destination = self.root / kind
                with self.approved(archive), self.assertRaises(ErroAcbrImpressora):
                    installer.instalar_runtime(archive, destination)
                self.assertFalse(destination.exists())
                self.assertFalse((self.root / "escape").exists())


if __name__ == "__main__":
    unittest.main()
