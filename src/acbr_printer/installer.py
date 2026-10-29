"""Instalação explícita de um artefato imutável e conferido, sem Node.js."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile

from .errors import ErroAcbrImpressora
from .runtime import RUNTIME_VERSION, cache_directory, checked_member, platform_key, resolve_runtime

APPROVED_FILE = "acbr-printer-runtime-0.1.2-local.1.tgz"
APPROVED_URL = None  # Esta revisão ainda não tem release pública.
APPROVED_SHA256 = "0aba5fb78b40099427a74076a70d4e8edcda3b8fa243a0f31a5db5c8d2e64093"
APPROVED_BYTES = 71442624


def _verify_archive(archive: Path) -> None:
    try:
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if archive.stat().st_size != APPROVED_BYTES or digest != APPROVED_SHA256:
            raise ValueError()
    except (OSError, ValueError):
        raise ErroAcbrImpressora("ARTEFATO_DIVERGENTE", "O arquivo não corresponde ao runtime auditado " + RUNTIME_VERSION + ".") from None


def _extract(archive: Path, destination: Path) -> None:
    prefix = "package/runtime/" + platform_key() + "/"
    members = set()
    output = set()
    total = 0
    with tarfile.open(archive, "r:gz") as package:
        for member in package:
            # Validate the whole archive, not only the selected platform.
            if (not member.isfile() or member.name in members or not member.name.startswith("package/")
                    or len(members) >= 10000 or member.size < 0 or member.size > 200 * 1024 * 1024):
                raise ValueError("Unsafe archive member")
            checked_member(destination, member.name)
            members.add(member.name)
            total += member.size
            if total > 300 * 1024 * 1024:
                raise ValueError("Archive exceeds extraction budget")
            if not member.name.startswith(prefix):
                continue
            name = member.name[len(prefix):]
            target = checked_member(destination, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = package.extractfile(member)
            if stream is None:
                raise ValueError("Missing stream")
            with stream, target.open("xb") as out:
                shutil.copyfileobj(stream, out, length=1024 * 1024)
            target.chmod(0o755 if name == "acbr-printer-worker" else 0o644)
            output.add(name)
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    if output != set(manifest.get("files", {})) | {"manifest.json"}:
        raise ValueError("Runtime inventory differs from extracted files")
    resolve_runtime(destination)


def instalar_runtime(arquivo: str | os.PathLike | None = None,
                     destino: str | os.PathLike | None = None) -> dict:
    """Instalação local explícita; nenhum download remoto nesta revisão."""
    if arquivo is None:
        raise ErroAcbrImpressora("RUNTIME_LOCAL_NAO_PUBLICADO", "Este runtime ainda não foi publicado. Use --arquivo com " + APPROVED_FILE + ".")
    destination = Path(destino) if destino is not None else cache_directory()
    if destination.is_symlink():
        raise ErroAcbrImpressora("DESTINO_INVALIDO", "O destino de instalação não pode ser um link.")
    destination = destination.absolute().resolve()
    if destination.exists():
        raise ErroAcbrImpressora("DESTINO_EXISTENTE", "O destino já existe; não será sobrescrito.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".acbr-printer-install-", dir=destination.parent)).resolve()
    try:
        archive = Path(arquivo)
        _verify_archive(archive)
        _extract(archive, stage)
        # Rename only after complete verification; never replace an existing install.
        if destination.exists():
            raise ErroAcbrImpressora("DESTINO_EXISTENTE", "O destino surgiu durante a instalação; nada será sobrescrito.")
        stage.rename(destination)
        return {"runtimeDirectory": str(destination), "platform": platform_key(),
                "runtimeVersion": RUNTIME_VERSION, "sha256": APPROVED_SHA256,
                "source": APPROVED_FILE, "downloadExecutado": False}
    except ErroAcbrImpressora:
        raise
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError):
        raise ErroAcbrImpressora("INSTALACAO_RUNTIME_FALHOU", "Não foi possível instalar e conferir o runtime; o destino não foi alterado.") from None
    finally:
        # Only the private staging directory created above can be removed.
        if stage.exists() and stage.parent == destination.parent and stage.name.startswith(".acbr-printer-install-"):
            shutil.rmtree(stage)
