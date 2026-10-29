"""PDF local por padrão; --enviar imprime uma via pelo spooler informado."""
import argparse
import json
from pathlib import Path

from acbr_printer import criar_impressora

parser = argparse.ArgumentParser()
parser.add_argument("xml")
parser.add_argument("--saida", default="danfe.pdf")
parser.add_argument("--impressora", default="ELGIN")
parser.add_argument("--largura", type=float, default=72)
parser.add_argument("--runtime-directory")
parser.add_argument("--enviar", action="store_true")
args = parser.parse_args()
config = {"modo": "spooler", "impressora": args.impressora}
if args.runtime_directory:
    config["runtimeDirectory"] = args.runtime_directory
xml = Path(args.xml).read_bytes()
with criar_impressora(config) as printer:
    result = printer.danfe_pdf(xml, {"larguraPapel": args.largura})
    if not result["sucesso"]:
        raise RuntimeError(result.get("mensagem", "Falha na geração do PDF."))
    with open(args.saida, "xb") as output:
        output.write(result["pdf"])
    print(json.dumps({"pdf": args.saida, "bytes": len(result["pdf"]), "envioFisico": False}))
    if args.enviar:
        result = printer.imprimir_danfe(xml, {"copias": 1, "larguraPapel": args.largura})
        print(json.dumps(result, ensure_ascii=False))
        if not result["sucesso"]:
            raise SystemExit(1)
