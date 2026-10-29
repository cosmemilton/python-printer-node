"""Resolução local e conferência de integridade do worker compartilhado."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import struct
import sys

from .errors import ErroAcbrImpressora

SOURCE_REVISION = 48590
RUNTIME_VERSION = "0.1.2-local.1"


def platform_key() -> str:
    if (sys.platform not in ("linux", "win32") or struct.calcsize("P") != 8
            or platform.machine().lower() not in ("x86_64", "amd64", "x64")):
        raise ErroAcbrImpressora("PLATAFORMA_NAO_SUPORTADA", "Use Python e runtime Windows ou Linux x64.")
    return sys.platform + "-x64"


def cache_directory() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) if sys.platform == "win32" else Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "acbr-printer-python" / RUNTIME_VERSION / platform_key()


def checked_member(root: Path, name: str) -> Path:
    if (not isinstance(name, str) or not name or len(name) > 2048 or "\\" in name
            or ":" in name or "\x00" in name or name.startswith("/")
            or any(part in ("", ".", "..") for part in name.split("/"))):
        raise ErroAcbrImpressora("RUNTIME_INVALIDO", "Caminho inválido no manifesto do runtime.")
    parts = PurePosixPath(name).parts
    target = root.joinpath(*parts)
    # Reject links in every component, including a linked subdirectory.
    current = root
    for part in parts:
        current /= part
        if current.is_symlink():
            raise ErroAcbrImpressora("RUNTIME_INVALIDO", "Links não são permitidos no runtime.")
    if not target.resolve().is_relative_to(root):
        raise ErroAcbrImpressora("RUNTIME_INVALIDO", "Caminho saiu do runtime.")
    return target


def resolve_runtime(directory: str | os.PathLike | None = None) -> tuple[Path, Path]:
    key = platform_key()
    if directory is None:
        candidates = [Path(__file__).resolve().parents[2] / "runtime" / key,
                      Path(__file__).resolve().parent / "runtime" / key, cache_directory()]
        directory = next((p for p in candidates if (p / "manifest.json").is_file()), None)
        if directory is None:
            raise ErroAcbrImpressora("RUNTIME_AUSENTE", "Instale o runtime explicitamente ou informe runtimeDirectory.")
    root = Path(directory)
    if root.is_symlink():
        raise ErroAcbrImpressora("RUNTIME_INVALIDO", "O diretório do runtime não pode ser um link.")
    try:
        root = root.resolve(strict=True)
        raw = root / "manifest.json"
        if raw.is_symlink() or raw.stat().st_size > 2 * 1024 * 1024:
            raise ValueError()
        manifest = json.loads(raw.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, RecursionError):
        raise ErroAcbrImpressora("RUNTIME_AUSENTE", "Manifesto do runtime ausente ou inválido.") from None
    inventory = manifest.get("files") if isinstance(manifest, dict) else None
    executable = manifest.get("executable") if isinstance(manifest, dict) else None
    if (not isinstance(manifest, dict) or type(manifest.get("formatVersion")) is not int
            or manifest["formatVersion"] != 1 or manifest.get("sourceRevision") != SOURCE_REVISION
            or manifest.get("platform") != sys.platform or manifest.get("arch") != "x64"
            or not isinstance(inventory, dict) or not 1 <= len(inventory) <= 10000
            or not isinstance(executable, str) or executable not in inventory):
        raise ErroAcbrImpressora("RUNTIME_INVALIDO", "Revisão, plataforma ou inventário incompatíveis.")
    for name, digest in inventory.items():
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ErroAcbrImpressora("RUNTIME_INVALIDO", "Hash inválido no manifesto.")
        target = checked_member(root, name)
        try:
            if not target.is_file():
                raise OSError()
            with target.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
        except OSError:
            raise ErroAcbrImpressora("RUNTIME_INCOMPLETO", "Arquivo necessário ao runtime ausente.") from None
        if actual != digest:
            raise ErroAcbrImpressora("RUNTIME_ALTERADO", "Arquivo do runtime diverge dos hashes distribuídos.")
    return root, checked_member(root, executable)
