"""Processo de protocolo para testes, sem acesso a impressora ou rede."""
import base64
import json
import os
import sys
import time

request = json.loads(sys.stdin.buffer.readline())
text = request.get("texto", "")
command = request["comando"]
if text == "delay":
    time.sleep(0.3)
if text.startswith("timeout"):
    if text == "timeout-marker":
        print(json.dumps({"tipo": "envioIniciado", "id": request["id"]}), flush=True)
    time.sleep(5)
if text == "oversized":
    sys.stdout.buffer.write(b"X" * (33 * 1024 * 1024))
    sys.stdout.buffer.flush()
    time.sleep(5)
if text == "stderr-oversized":
    sys.stderr.buffer.write(b"X" * (1024 * 1024 + 1))
    sys.stderr.buffer.flush()
    time.sleep(5)
if text == "deep-json":
    sys.stdout.buffer.write(b"[" * 2000 + b"0" + b"]" * 2000 + b"\n")
    raise SystemExit()
physical = command in ("imprimirTexto", "imprimirDanfe")
if physical:
    print(json.dumps({"tipo": "envioIniciado", "id": request["id"]}), flush=True)
reply = {"versao": 1, "sourceRevision": 48590, "id": request["id"], "sucesso": True,
         "estado": "ENVIADO" if physical else "GERADO" if command in ("gerarEscpos", "danfePdf") else "PREPARADO",
         "envioIniciado": physical}
if command == "gerarEscpos":
    reply["dadosBase64"] = base64.b64encode(text.encode("utf-8")).decode()
if command == "danfePdf":
    reply["pdfBase64"] = base64.b64encode(b"%PDF-test").decode()
if command == "capacidades":
    reply["capacidades"] = {"spoolerFortes": True, "danfePdf": True, "danfeEscpos": True}
if command == "listarImpressoras":
    reply["impressoras"] = ["IMPRESSORA-FICTICIA"]
if text == "wrong-id":
    reply["id"] = "other"
if text == "wrong-revision":
    reply["sourceRevision"] = 123
if text == "bad-base64":
    reply["dadosBase64"] = "QQ"
if text == "invalid-state":
    reply["estado"] = "IMPRESSO"
encoded = (json.dumps(reply, ensure_ascii=False) + "\n").encode()
if text == "fragmented":
    for byte in encoded:
        sys.stdout.buffer.write(bytes([byte]))
        sys.stdout.buffer.flush()
else:
    sys.stdout.buffer.write(encoded)
if text == "duplicate":
    sys.stdout.buffer.write(encoded)
if text == "trailing":
    sys.stdout.buffer.write(b"not terminated")
sys.stdout.buffer.flush()
if text == "nonzero":
    raise SystemExit(9)
