"""Teste explícito do motor real; somente bytes, PDF e porta FILE:."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from acbr_printer import criar_impressora


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True)
    args = parser.parse_args()
    fixtures = Path(__file__).parent / "fixtures"
    data = json.loads((fixtures / "python.json").read_text(encoding="utf-8"))
    config = dict(data["configuracaoAvancada"])
    config.pop("porta")
    config["runtimeDirectory"] = args.runtime
    with criar_impressora(config) as printer:
        capabilities = printer.capacidades()
        assert capabilities["sucesso"] and capabilities["capacidades"]["danfePdf"]
        advanced = printer.gerar_escpos(data["avancado"])
        assert advanced["sucesso"] and advanced["envioIniciado"] is False
        for name, encoded in data["comandosHex"].items():
            assert bytes.fromhex(encoded) in advanced["dados"], name
        assert advanced["dados"].count(bytes.fromhex(data["comandosHex"]["corteTotal"])) == 1
        assert hashlib.sha256(advanced["dados"]).hexdigest() == data["referenciaNode"]["sha256"]
        pdfs = {}
        for filename in ("nfce-65-homologacao.xml", "nfe-55-sintetica-pdf.xml"):
            pdf = printer.danfe_pdf((fixtures / filename).read_bytes(), {"larguraPapel": 72})
            assert pdf["sucesso"] and pdf["envioIniciado"] is False and pdf["pdf"].startswith(b"%PDF-")
            pdfs[filename] = len(pdf["pdf"])
    with tempfile.TemporaryDirectory(prefix="acbr-printer-python-native-") as temporary:
        target = Path(temporary).resolve() / "nfce-escpos.bin"
        # FILE is an explicit file target, never a device or spooler queue.
        with criar_impressora(modo="escpos", porta="FILE:" + str(target), tipo=8,
                             runtime_directory=args.runtime) as printer:
            result = printer.imprimir_danfe((fixtures / "nfce-65-homologacao.xml").read_bytes(), {"copias": 1})
            assert result["sucesso"]
        assert b"Documento Auxiliar" in target.read_bytes()
    print(json.dumps({"nativeOffline": "OK", "advancedBytes": len(advanced["dados"]), "pdfBytes": pdfs, "hardware": False}))


if __name__ == "__main__":
    main()
