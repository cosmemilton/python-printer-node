"""Cliente síncrono JSONL. Cada operação usa um processo nativo isolado."""
from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from typing import Any
import uuid
import weakref

from .errors import ErroAcbrImpressora
from .runtime import SOURCE_REVISION, resolve_runtime

PROTOCOL_VERSION = 1
INPUT_LIMIT = 2 * 1024 * 1024
RESPONSE_LIMIT = 32 * 1024 * 1024
STDERR_LIMIT = 1024 * 1024
TIPOS_IMPRESSORA = {"Texto": 0, "EscPosStar": 8}
_PHYSICAL = {"imprimirTexto", "imprimirDanfe"}
_STATES = {"PREPARADO", "GERADO", "ENVIADO", "ERRO"}


class _Gate:
    def __init__(self) -> None:
        self.lock = threading.Lock()


_gates: weakref.WeakValueDictionary[str, _Gate] = weakref.WeakValueDictionary()
_gates_guard = threading.Lock()


def _error(code: str, message: str, uncertain: bool = False) -> ErroAcbrImpressora:
    return ErroAcbrImpressora(code, message, uncertain)


def _integer(value: Any, minimum: int, maximum: int, field: str, code: str = "CONFIGURACAO_INVALIDA") -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise _error(code, f"{field} deve ser um inteiro entre {minimum} e {maximum}.")
    return value


def _decode(value: Any, limit: int, code: str, allow_empty: bool = False) -> bytes:
    if not isinstance(value, str) or (not value and not allow_empty) or len(value) > ((limit + 2) // 3) * 4:
        raise _error(code, "Conteúdo base64 inválido ou acima do limite.")
    try:
        result = base64.b64decode(value, validate=True)
        if len(result) > limit or base64.b64encode(result).decode("ascii") != value:
            raise ValueError()
        return result
    except (ValueError, binascii.Error, UnicodeError):
        raise _error(code, "Conteúdo base64 inválido ou acima do limite.") from None


def _xml(value: Any) -> str:
    try:
        if isinstance(value, str):
            data = value.encode("utf-8", errors="strict")
        elif isinstance(value, (bytes, bytearray, memoryview)):
            data = bytes(value)
        elif isinstance(value, Mapping):
            data = _decode(value.get("xmlBase64"), INPUT_LIMIT, "XML_INVALIDO")
        else:
            raise ValueError()
        if not 0 < len(data) <= INPUT_LIMIT or not data.decode("utf-8", errors="strict").strip():
            raise ValueError()
    except (ValueError, UnicodeError):
        raise _error("XML_INVALIDO", "Informe XML UTF-8 não vazio com até 2 MiB.") from None
    return base64.b64encode(data).decode("ascii")


def _text(value: Any) -> str:
    try:
        if not isinstance(value, str) or not value or len(value.encode("utf-8")) > INPUT_LIMIT:
            raise ValueError()
        if any(ord(char) < 32 and char not in "\t\r\n" for char in value):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise _error("TEXTO_INVALIDO", "Informe texto UTF-8 sem comandos binários, com até 2 MiB.") from None
    return value


def _danfe_options(value: Mapping | None) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) - {"copias", "larguraPapel", "largura_papel"}:
        raise _error("OPERACAO_INVALIDA", "Opções DANFE inválidas ou desconhecidas.")
    if "larguraPapel" in value and "largura_papel" in value:
        raise _error("OPERACAO_INVALIDA", "Não informe o mesmo campo em duas grafias.")
    result = {}
    if "copias" in value:
        result["copias"] = _integer(value["copias"], 1, 99, "copias", "OPERACAO_INVALIDA")
    width = value.get("larguraPapel", value.get("largura_papel"))
    if "larguraPapel" in value or "largura_papel" in value:
        if type(width) not in (int, float) or not 40 <= width <= 300 or not math.isfinite(width):
            raise _error("OPERACAO_INVALIDA", "larguraPapel deve estar entre 40 e 300 milímetros.")
        result["larguraPapel"] = width
    return result


def _strict_json(line: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result
    def invalid_constant(_):
        raise ValueError("constant")
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("float")
        return number
    result = json.loads(line.decode("utf-8", errors="strict"), object_pairs_hook=pairs, parse_constant=invalid_constant, parse_float=finite_float)
    if not isinstance(result, dict):
        raise ValueError("object")
    return result


def _result(frame: dict, request: dict, sending: bool) -> dict:
    command = request["comando"]
    if (type(frame.get("versao")) is not int or frame["versao"] != PROTOCOL_VERSION
            or type(frame.get("sourceRevision")) is not int or frame["sourceRevision"] != SOURCE_REVISION
            or type(frame.get("sucesso")) is not bool or frame.get("estado") not in _STATES
            or type(frame.get("envioIniciado")) is not bool or sending and not frame["envioIniciado"]
            or "resultadoIncerto" in frame and type(frame["resultadoIncerto"]) is not bool):
        raise ValueError()
    for name, maximum in (("codigo", 128), ("mensagem", 8192)):
        if name in frame and (not isinstance(frame[name], str) or len(frame[name]) > maximum):
            raise ValueError()
    if ((frame["sucesso"] and (frame["estado"] == "ERRO" or frame.get("resultadoIncerto") is True))
            or (not frame["sucesso"] and frame["estado"] != "ERRO")
            or command not in _PHYSICAL and (sending or frame["envioIniciado"] or frame["estado"] == "ENVIADO")
            or frame["sucesso"] and command in _PHYSICAL and (frame["estado"] != "ENVIADO" or not frame["envioIniciado"])):
        raise ValueError()
    result = {name: frame[name] for name in ("versao", "id", "sourceRevision", "sucesso", "estado", "envioIniciado")}
    for name in ("codigo", "mensagem"):
        if name in frame:
            result[name] = frame[name]
    if frame.get("resultadoIncerto") is True or not frame["sucesso"] and frame["envioIniciado"]:
        result["resultadoIncerto"] = True
    for encoded, decoded, allow_empty in (("dadosBase64", "dados", True), ("pdfBase64", "pdf", False)):
        if encoded in frame:
            result[decoded] = _decode(frame[encoded], RESPONSE_LIMIT, "RESPOSTA_INVALIDA", allow_empty)
            result[encoded] = frame[encoded]
    if "impressoras" in frame:
        names = frame["impressoras"]
        if not isinstance(names, list) or len(names) > 10000 or any(not isinstance(n, str) or len(n) > 1024 or "\0" in n for n in names):
            raise ValueError()
        result["impressoras"] = list(names)
    if "capacidades" in frame:
        if not isinstance(frame["capacidades"], dict):
            raise ValueError()
        result["capacidades"] = frame["capacidades"]
    needed = {"gerarEscpos": "dados", "danfePdf": "pdf", "capacidades": "capacidades", "listarImpressoras": "impressoras"}.get(command)
    if frame["sucesso"] and needed and needed not in result:
        raise ValueError()
    return result


class Impressora:
    """Fachada síncrona; operações do mesmo destino são serializadas no processo."""
    def __init__(self, configuracao: Mapping | None = None, **options: Any) -> None:
        if configuracao is None:
            configuracao = {}
        if not isinstance(configuracao, Mapping) or set(configuracao) & set(options):
            raise _error("CONFIGURACAO_INVALIDA", "Informe uma configuração sem campos duplicados.")
        aliases = {"linhas_entre_cupons": "linhasEntreCupons", "interpretar_tags": "interpretarTags", "cortar_papel": "cortarPapel",
                   "runtime_directory": "runtimeDirectory", "timeout_ms": "timeoutMs", "limite_fila": "limiteFila"}
        values = {}
        allowed = {"modo", "porta", "impressora", "tipo", "colunas", "linhasEntreCupons", "interpretarTags", "cortarPapel", "runtimeDirectory", "timeoutMs", "limiteFila"}
        for name, value in {**configuracao, **options}.items():
            name = aliases.get(name, name)
            if name not in allowed or name in values:
                raise _error("CONFIGURACAO_INVALIDA", "Há campos desconhecidos ou duplicados na configuração.")
            values[name] = value
        mode, kind = values.get("modo", "escpos"), values.get("tipo", 0)
        if mode not in ("escpos", "spooler") or type(kind) is not int or kind not in (0, 8):
            raise _error("CONFIGURACAO_INVALIDA", "modo deve ser escpos/spooler e tipo deve ser 0/8.")
        self._config = {"modo": mode, "tipo": kind,
                        "colunas": _integer(values.get("colunas", 48), 1, 200, "colunas"),
                        "linhasEntreCupons": _integer(values.get("linhasEntreCupons", 0), 0, 100, "linhasEntreCupons")}
        for name in ("interpretarTags", "cortarPapel"):
            value = values.get(name, False)
            if type(value) is not bool:
                raise _error("CONFIGURACAO_INVALIDA", f"{name} deve ser booleano.")
            self._config[name] = value
        for name in ("porta", "impressora"):
            if name in values:
                value = values[name]
                if not isinstance(value, str) or not value.strip() or len(value) > 1024 or re.search(r"[\x00-\x1f\x7f]", value):
                    raise _error("CONFIGURACAO_INVALIDA", f"Informe um destino válido em {name}.")
                self._config[name] = value.strip()
        self._runtime_directory = values.get("runtimeDirectory")
        if self._runtime_directory is not None and (not isinstance(self._runtime_directory, (str, os.PathLike)) or not str(self._runtime_directory).strip() or "\0" in str(self._runtime_directory)):
            raise _error("CONFIGURACAO_INVALIDA", "runtimeDirectory inválido.")
        self._timeout = _integer(values.get("timeoutMs", 30000), 1, 120000, "timeoutMs") / 1000
        self._capacity = _integer(values.get("limiteFila", 32), 0, 1000, "limiteFila")
        self._condition = threading.Condition()
        self._closed = False
        self._cleanup_failed = False
        self._waiting = 0
        self._busy = 0
        self._active: subprocess.Popen | None = None
        self._runtime: tuple[Path, Path] | None = None
        target = self._config.get("impressora" if mode == "spooler" else "porta", str(uuid.uuid4()))
        if sys.platform == "win32":
            target = target.replace("/", "\\").lower()
            unc = re.fullmatch(r"\\\\([^\\]+)\\([^\\]+)", target)
            if unc and unc[1] in {"localhost", ".", "127.0.0.1", os.environ.get("COMPUTERNAME", "").lower()}:
                target = unc[2]
        with _gates_guard:
            key = sys.platform + ":" + target
            self._gate = _gates.get(key)
            if self._gate is None:
                self._gate = _Gate()
                _gates[key] = self._gate

    def _check_open(self) -> None:
        if self._closed:
            raise ErroAcbrImpressora("IMPRESSORA_FECHADA", "A instância foi encerrada.", falha_limpeza=self._cleanup_failed)

    def _request(self, command: str, **data: Any) -> dict:
        with self._condition:
            self._check_open()
        if command in _PHYSICAL:
            target = self._config.get("impressora" if self._config["modo"] == "spooler" else "porta")
            if not target:
                raise _error("DESTINO_AUSENTE", "Informe a porta POS ou o nome da fila do spooler.")
            if sys.platform != "win32" and target.startswith(("\\\\", "//")):
                raise _error("DESTINO_WINDOWS_REQUER_PYTHON_WINDOWS", "Destinos UNC Windows exigem Python e worker no Windows.")
        request = {"versao": PROTOCOL_VERSION, "id": str(uuid.uuid4()), "comando": command,
                   "config": dict(self._config), **data}
        acquired = self._gate.lock.acquire(blocking=False)
        if not acquired:
            with self._condition:
                self._check_open()
                if self._waiting >= self._capacity:
                    raise _error("FILA_CHEIA", "A fila desta instância está cheia.")
                self._waiting += 1
            try:
                while not acquired:
                    with self._condition:
                        self._check_open()
                    acquired = self._gate.lock.acquire(timeout=0.05)
            finally:
                with self._condition:
                    self._waiting -= 1
                    self._condition.notify_all()
        try:
            with self._condition:
                self._check_open()
                self._busy += 1
            try:
                return self._execute(request)
            finally:
                with self._condition:
                    self._active = None
                    self._busy -= 1
                    self._condition.notify_all()
        finally:
            self._gate.lock.release()

    def _execute(self, request: dict) -> dict:
        if self._runtime is None:
            self._runtime = resolve_runtime(self._runtime_directory)
        root, executable = self._runtime
        with self._condition:
            self._check_open()
        environment = {key: os.environ[key] for key in ("PATH", "Path", "SystemRoot", "WINDIR", "TEMP", "TMP", "HOME", "LANG", "LC_ALL", "DISPLAY", "XDG_RUNTIME_DIR") if key in os.environ}
        if sys.platform == "win32":
            inherited = environment.pop("Path", environment.get("PATH", ""))
            environment["PATH"] = str(root / "lib") + ";" + str(root) + ";" + inherited
        else:
            environment["LD_LIBRARY_PATH"] = str(root / "lib")
        payload = (json.dumps(request, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        try:
            process = subprocess.Popen([str(executable)], cwd=root, env=environment, shell=False,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        except OSError:
            raise _error("FALHA_INICIAR_MOTOR", "Não foi possível iniciar o motor de impressão.") from None
        with self._condition:
            self._active = process
        state: dict[str, Any] = {"sending": False, "written": False, "response": None, "error": None}
        guard = threading.Lock()
        failure = threading.Event()
        physical = request["comando"] in _PHYSICAL

        def uncertain() -> bool:
            return physical and (state["sending"] or state["written"])

        def fail(code: str, message: str) -> None:
            with guard:
                if state["error"] is None:
                    state["error"] = _error(code, message, uncertain())
            failure.set()

        def stdout_reader() -> None:
            rest = bytearray()
            count = 0
            try:
                assert process.stdout is not None
                while chunk := process.stdout.read1(8192):
                    count += len(chunk)
                    if count > RESPONSE_LIMIT:
                        fail("RESPOSTA_EXCESSIVA", "O motor excedeu o limite de resposta.")
                        return
                    previous_length = len(rest)
                    rest.extend(chunk)
                    index = rest.find(10, previous_length)
                    while index >= 0:
                        line = bytes(rest[:index])
                        del rest[:index + 1]
                        if not line:
                            index = rest.find(10)
                            continue
                        frame = _strict_json(line)
                        if frame.get("id") != request["id"] or state["response"] is not None:
                            raise ValueError()
                        if frame.get("tipo") == "envioIniciado":
                            if not physical:
                                raise ValueError()
                            state["sending"] = True
                        else:
                            state["response"] = _result(frame, request, state["sending"])
                        index = rest.find(10)
                if rest:
                    raise ValueError()
            except (OSError, ValueError, KeyError, TypeError, RecursionError, ErroAcbrImpressora):
                fail("RESPOSTA_INVALIDA", "O motor retornou protocolo de impressão inválido.")

        def stderr_reader() -> None:
            count = 0
            try:
                assert process.stderr is not None
                while chunk := process.stderr.read1(8192):
                    count += len(chunk)
                    if count > STDERR_LIMIT:
                        fail("RESPOSTA_EXCESSIVA", "O motor excedeu o limite de diagnóstico.")
                        return
            except OSError:
                fail("FALHA_PIPE", "Falha na comunicação com o motor.")

        def writer() -> None:
            try:
                assert process.stdin is not None
                state["written"] = True
                process.stdin.write(payload)
                process.stdin.close()
            except (OSError, ValueError):
                fail("FALHA_PIPE", "Falha na comunicação com o motor.")

        threads = [threading.Thread(target=fn, daemon=True) for fn in (stdout_reader, stderr_reader, writer)]
        for thread in threads:
            thread.start()
        deadline = time.monotonic() + self._timeout
        try:
            while process.poll() is None:
                if failure.is_set():
                    break
                with self._condition:
                    closed = self._closed
                if closed:
                    fail("IMPRESSORA_FECHADA", "A instância foi encerrada durante a operação.")
                    break
                if time.monotonic() >= deadline:
                    fail("TIMEOUT_MOTOR", "O motor excedeu o prazo. Confira o destino antes de repetir.")
                    break
                failure.wait(min(0.01, max(0.0, deadline - time.monotonic())))
            if process.poll() is None:
                process.kill()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                with self._condition:
                    self._cleanup_failed = self._closed = True
                raise ErroAcbrImpressora("FALHA_ENCERRAR_MOTOR", "Não foi possível confirmar o encerramento do motor.", uncertain(), True) from None
            for thread in threads:
                thread.join(timeout=1)
            if any(thread.is_alive() for thread in threads):
                with self._condition:
                    self._cleanup_failed = self._closed = True
                raise ErroAcbrImpressora("FALHA_ENCERRAR_MOTOR", "Não foi possível confirmar o encerramento das pipes.", uncertain(), True)
            if state["error"]:
                # Written bytes can make a later reader error physically uncertain.
                state["error"].resultado_incerto |= uncertain()
                raise state["error"]
            if process.returncode != 0 or state["response"] is None:
                raise _error("FALHA_MOTOR", "O motor encerrou sem uma resposta válida.", uncertain())
            return state["response"]
        finally:
            if process.poll() is None:
                try:
                    process.kill()
                    process.wait(timeout=1)
                except (OSError, subprocess.TimeoutExpired):
                    with self._condition:
                        self._cleanup_failed = self._closed = True
            # A buffered stream close can wait on a reader/writer lock. If a
            # thread did not terminate, fail closed without blocking indefinitely.
            if not any(thread.is_alive() for thread in threads):
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream:
                        try:
                            stream.close()
                        except OSError:
                            pass

    def capacidades(self) -> dict:
        return self._request("capacidades")

    def listar_impressoras(self) -> dict:
        return self._request("listarImpressoras")

    def gerar_escpos(self, texto: str) -> dict:
        return self._request("gerarEscpos", texto=_text(texto))

    def imprimir_texto(self, texto: str) -> dict:
        return self._request("imprimirTexto", texto=_text(texto))

    def danfe_pdf(self, xml: Any, opcoes: Mapping | None = None) -> dict:
        options = _danfe_options(opcoes)
        return self._request("danfePdf", xmlBase64=_xml(xml), **({"opcoes": options} if options is not None else {}))

    def imprimir_danfe(self, xml: Any, opcoes: Mapping | None = None) -> dict:
        options = _danfe_options(opcoes)
        return self._request("imprimirDanfe", xmlBase64=_xml(xml), **({"opcoes": options} if options is not None else {}))

    def fechar(self) -> None:
        with self._condition:
            self._closed = True
            process = self._active
            if process is not None and process.poll() is None:
                try:
                    process.kill()
                except OSError:
                    pass
            deadline = time.monotonic() + 4
            while self._busy or self._waiting:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._cleanup_failed = True
                    raise ErroAcbrImpressora("FALHA_ENCERRAR_MOTOR", "Não foi possível confirmar o encerramento da operação.", falha_limpeza=True)
                self._condition.wait(timeout=remaining)

    def __enter__(self) -> Impressora:
        with self._condition:
            self._check_open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.fechar()

    listarImpressoras = listar_impressoras
    gerarEscpos = gerar_escpos
    imprimirTexto = imprimir_texto
    danfePdf = danfe_pdf
    imprimirDanfe = imprimir_danfe


def criar_impressora(configuracao: Mapping | None = None, **options: Any) -> Impressora:
    return Impressora(configuracao, **options)


criarImpressora = criar_impressora
