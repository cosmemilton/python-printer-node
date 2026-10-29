"""Gera bytes por padrão. --enviar é uma solicitação física explícita."""
import argparse
import json
from pathlib import Path

from acbr_printer import criar_impressora

parser = argparse.ArgumentParser()
parser.add_argument("--runtime-directory")
parser.add_argument("--porta", default=r"\\localhost\elgin")
parser.add_argument("--avancado", action="store_true")
parser.add_argument("--enviar", action="store_true")
args = parser.parse_args()
fixture = json.loads((Path(__file__).parents[1] / "tests/fixtures/python.json").read_text(encoding="utf-8"))
config = dict(fixture["configuracaoAvancada"]) if args.avancado else {"tipo": 0}
config["porta"] = args.porta
if args.runtime_directory:
    config["runtimeDirectory"] = args.runtime_directory
text = fixture["avancado"] if args.avancado else fixture["texto"]
with criar_impressora(config) as printer:
    generated = printer.gerar_escpos(text)
    if not generated["sucesso"]:
        raise RuntimeError(generated.get("mensagem", "Falha na geração."))
    print(json.dumps({"bytesGerados": len(generated["dados"]), "envioFisico": False}))
    if args.enviar:
        result = printer.imprimir_texto(text)
        print(json.dumps({k: v for k, v in result.items() if k not in ("dados", "dadosBase64", "pdf", "pdfBase64")}))
        if not result["sucesso"]:
            raise SystemExit(1)
