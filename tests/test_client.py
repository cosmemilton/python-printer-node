import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from acbr_printer import ErroAcbrImpressora, criar_impressora
from acbr_printer import client
from acbr_printer.runtime import resolve_runtime

REAL_POPEN = subprocess.Popen


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="acbr-printer-python-test-")
        self.root = Path(self.temporary.name).resolve()
        worker = self.root / "fake_worker.py"
        shutil.copyfile(Path(__file__).parent / "fake_worker.py", worker)
        worker.chmod(0o755)
        manifest = {"formatVersion": 1, "sourceRevision": 48590, "platform": sys.platform,
                    "arch": "x64", "executable": worker.name,
                    "files": {worker.name: hashlib.sha256(worker.read_bytes()).hexdigest()}}
        (self.root / "manifest.json").write_text(json.dumps(manifest))
        self.launches = []
        def launch(argv, **kwargs):
            self.launches.append((list(argv), kwargs))
            self.assertEqual(argv, [str(worker)])
            self.assertFalse(kwargs["shell"])
            self.assertNotIn("NPM_TOKEN", kwargs["env"])
            return REAL_POPEN([sys.executable, "-u", str(worker)], **kwargs)
        self.patcher = patch.object(client.subprocess, "Popen", side_effect=launch)
        self.patcher.start()
        self.instances = []

    def tearDown(self):
        for instance in self.instances:
            instance.fechar()
        self.patcher.stop()
        self.temporary.cleanup()

    def printer(self, **options):
        instance = criar_impressora({"runtimeDirectory": self.root, **options})
        self.instances.append(instance)
        return instance

    def assert_code(self, code, action, uncertain=False):
        with self.assertRaises(ErroAcbrImpressora) as raised:
            action()
        self.assertEqual(raised.exception.codigo, code)
        self.assertEqual(raised.exception.resultado_incerto, uncertain)
        return raised.exception

    def test_queries_and_utf8_bytes_use_only_stdin(self):
        with self.printer() as printer:
            self.assertTrue(printer.capacidades()["capacidades"]["danfePdf"])
            self.assertEqual(printer.listar_impressoras()["impressoras"], ["IMPRESSORA-FICTICIA"])
            text = "Café São José — teste\n"
            result = printer.gerar_escpos(text)
            self.assertEqual(result["dados"], text.encode())
            self.assertFalse(result["envioIniciado"])
        self.assertEqual(len(self.launches), 3)
        self.assert_code("IMPRESSORA_FECHADA", printer.capacidades)

    def test_aliases_and_fragmented_response(self):
        printer = self.printer(tipo=8, cortar_papel=True, interpretar_tags=True)
        result = printer.gerarEscpos("fragmented")
        self.assertEqual(result["dados"], b"fragmented")
        self.assertEqual(printer._config["tipo"], 8)
        self.assertTrue(printer._config["cortarPapel"])

    def test_xml_bytes_and_result_mapping_pdf_without_physical_send(self):
        printer = self.printer(modo="spooler")
        xml = b"<NFe/>"
        for value in [xml, xml.decode(), {"xmlBase64": base64.b64encode(xml).decode(), "sucesso": True}]:
            result = printer.danfe_pdf(value, {"largura_papel": 72})
            self.assertEqual(result["pdf"], b"%PDF-test")
            self.assertFalse(result["envioIniciado"])

    def test_configuration_rejects_wrong_types_and_unknown_fields(self):
        for values in [{"tipo": True}, {"tipo": 1}, {"colunas": False}, {"cortarPapel": 1}, {"modo": "raw"}, {"margemSuperior": 10}, {"timeoutMs": 0}, {"porta": "bad\x00name"}, {"cortar_papel": True, "cortarPapel": False}]:
            with self.subTest(values=values):
                self.assert_code("CONFIGURACAO_INVALIDA", lambda: criar_impressora(values))
        self.assertEqual(self.launches, [])

    def test_danfe_invalid_options_and_xml_do_not_spawn(self):
        printer = self.printer()
        for options in [{"larguraPapel": 10 ** 1000}, {"larguraPapel": float("nan")}, {"larguraPapel": True}, {"copias": 0}, {"margemSuperior": 3}]:
            self.assert_code("OPERACAO_INVALIDA", lambda: printer.danfe_pdf(b"<NFe/>", options))
        for xml in [b"", b"\xff", {"xmlBase64": "QQ"}, 1, b"x" * (2 * 1024 * 1024 + 1)]:
            self.assert_code("XML_INVALIDO", lambda: printer.danfe_pdf(xml))
        for text in ["", "x\x1bcommand", "x" * (2 * 1024 * 1024 + 1)]:
            self.assert_code("TEXTO_INVALIDO", lambda: printer.gerar_escpos(text))
        self.assertEqual(self.launches, [])

    def test_unc_destinations_require_windows_before_start(self):
        if sys.platform == "win32":
            self.skipTest("UNC Windows é testado pelo fluxo físico explícito, não aqui.")
        self.assert_code("DESTINO_WINDOWS_REQUER_PYTHON_WINDOWS", lambda: self.printer(porta=r"\\localhost\elgin").imprimir_texto("test"))
        self.assertEqual(self.launches, [])

    def test_physical_fake_response_tracks_send_without_hardware(self):
        result = self.printer(porta="FAKE-ONLY").imprimir_texto("fake transport")
        self.assertEqual(result["estado"], "ENVIADO")
        self.assertTrue(result["envioIniciado"])

    def test_invalid_protocol_replies_are_rejected(self):
        for text in ["wrong-id", "wrong-revision", "bad-base64", "invalid-state", "duplicate", "trailing", "deep-json"]:
            with self.subTest(text=text):
                self.assert_code("RESPOSTA_INVALIDA", lambda: self.printer().gerar_escpos(text))
        self.assert_code("FALHA_MOTOR", lambda: self.printer().gerar_escpos("nonzero"))

    def test_timeout_is_bounded_and_never_retried(self):
        for physical in (False, True):
            printer = self.printer(timeoutMs=150, porta="FAKE-ONLY")
            start = time.monotonic()
            count = len(self.launches)
            action = lambda: printer.imprimir_texto("timeout-marker") if physical else printer.gerar_escpos("timeout")
            self.assert_code("TIMEOUT_MOTOR", action, uncertain=physical)
            self.assertLess(time.monotonic() - start, 2)
            self.assertEqual(len(self.launches), count + 1)

    def test_stdout_and_stderr_budgets_kill_process(self):
        for text in ("oversized", "stderr-oversized"):
            start = time.monotonic()
            self.assert_code("RESPOSTA_EXCESSIVA", lambda: self.printer().gerar_escpos(text))
            self.assertLess(time.monotonic() - start, 3)

    def test_manifest_tamper_missing_and_traversal_are_rejected(self):
        worker = self.root / "fake_worker.py"
        original = worker.read_bytes()
        worker.write_bytes(original + b"\n# tamper")
        self.assert_code("RUNTIME_ALTERADO", lambda: resolve_runtime(self.root))
        worker.write_bytes(original)
        manifest_file = self.root / "manifest.json"
        manifest = json.loads(manifest_file.read_text())
        manifest["files"]["../escape"] = "0" * 64
        manifest_file.write_text(json.dumps(manifest))
        self.assert_code("RUNTIME_INVALIDO", lambda: resolve_runtime(self.root))
        self.assertEqual(self.launches, [])

    def test_manifest_symlink_is_rejected(self):
        worker = self.root / "fake_worker.py"
        alternate = self.root / "alternate.py"
        shutil.copyfile(worker, alternate)
        worker.unlink()
        try:
            worker.symlink_to(alternate)
        except OSError:
            self.skipTest("Criação de symlink indisponível nesta conta Windows.")
        self.assert_code("RUNTIME_INVALIDO", lambda: resolve_runtime(self.root))

    def test_close_interrupts_current_operation_and_waits_for_process(self):
        printer = self.printer(porta="FAKE-ONLY")
        errors = []
        def execute():
            try:
                printer.imprimir_texto("timeout-marker")
            except ErroAcbrImpressora as error:
                errors.append(error)
        thread = threading.Thread(target=execute)
        thread.start()
        deadline = time.monotonic() + 2
        while (printer._active is None or not printer._active.stdin.closed) and time.monotonic() < deadline:
            time.sleep(0.005)
        printer.fechar()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].resultado_incerto)
        self.assert_code("IMPRESSORA_FECHADA", printer.capacidades)

    def test_shared_destination_is_serialized_and_queue_capacity_is_enforced(self):
        printer = self.printer(porta="SAME-DESTINATION", limiteFila=0)
        results = []
        thread = threading.Thread(target=lambda: results.append(printer.gerar_escpos("delay")))
        thread.start()
        deadline = time.monotonic() + 2
        while printer._active is None and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assert_code("FILA_CHEIA", lambda: printer.gerar_escpos("not sent"))
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0]["dados"], b"delay")
        self.assertEqual(len(self.launches), 1)


if __name__ == "__main__":
    unittest.main()
