from __future__ import annotations

import argparse
import json
import sys

from .client import criar_impressora
from .errors import ErroAcbrImpressora
from .installer import instalar_runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="acbr-printer-python", description="Cliente ACBr de impressão; sem envio físico automático.")
    commands = parser.add_subparsers(dest="command", required=True)
    install = commands.add_parser("instalar-runtime", aliases=["install-runtime"], help="Instalar explicitamente o runtime auditado")
    install.add_argument("--arquivo", help="Tarball local obrigatório enquanto esta revisão não tem release pública")
    install.add_argument("--destino", help="Novo diretório de instalação; nunca sobrescreve")
    capabilities = commands.add_parser("capacidades", help="Consultar capacidades sem imprimir")
    capabilities.add_argument("--runtime-directory")
    args = parser.parse_args(argv)
    try:
        if args.command in ("instalar-runtime", "install-runtime"):
            result = instalar_runtime(args.arquivo, args.destino)
        else:
            config = {"runtimeDirectory": args.runtime_directory} if args.runtime_directory else {}
            with criar_impressora(config) as printer:
                result = printer.capacidades()
                if not result["sucesso"]:
                    print(json.dumps(result, ensure_ascii=False))
                    return 1
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except ErroAcbrImpressora as error:
        print(json.dumps(error.to_dict(), ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
