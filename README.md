# ACBr Printer Python

Componente independente de impressão para Python 3.11+, Windows e Linux x64.
Usa ACBrPosPrinter para texto/ESC-POS e FortesReport para spooler, DANFE e PDF.
API Python local **0.1.0**, motor auditado **0.1.2-local.1** e revisão ACBr **48590**.
O projeto ainda está sendo preparado localmente; não afirma publicação no PyPI.

O módulo `acbr_printer` pode conviver com `acbr` do emissor `acbr-python`.
Os componentes não exigem a instalação um do outro. O XML é o ponto de integração.
Não é necessário Node.js, npm, Delphi ou um compilador para executar o cliente.
O projeto é independente do Projeto ACBr e usa ferramentas livres, sem ACBr Pro.

## Instalação local

```sh
python -m pip install .
```

O wheel contém o cliente Python. O runtime é instalado **explicitamente por
arquivo local**, sem rede ao importar, instalar ou usar este instalador:

```sh
python -m acbr_printer instalar-runtime --arquivo acbr-printer-runtime-0.1.2-local.1.tgz --destino ./runtime-local
python -m acbr_printer capacidades --runtime-directory ./runtime-local
```

O artefato local inclui os motores Windows e Linux com a correção do nome do
trabalho do relatório de texto FortesReport. Ele mede **71.442.624 bytes** e
o SHA256 esperado é `0aba5fb78b40099427a74076a70d4e8edcda3b8fa243a0f31a5db5c8d2e64093`.
Ainda não existe release pública dessa revisão: omitir `--arquivo` retorna
`RUNTIME_LOCAL_NAO_PUBLICADO`. Não há download ou fallback para o runtime Node
0.1.1. O nome Node no histórico do motor indica a origem do código, sem exigir
o interpretador Node na execução de PHP ou Python.
A extração recusa links, travessia de diretórios, duplicatas e arquivos excessivos.
Fontes e licenças do motor acompanham a extração, e cada arquivo é conferido pelo
manifesto antes da instalação e antes do primeiro uso de uma instância. Só a
plataforma atual é extraída e uma instalação anterior nunca é sobrescrita.
Se `--destino` for omitido, a instalação explícita usa o cache local do usuário.

## Primeiro cupom, sem imprimir

```python
from acbr_printer import criar_impressora

with criar_impressora(tipo=0, runtime_directory="./runtime-local") as impressora:
    resultado = impressora.gerar_escpos("TESTE NAO FISCAL\nACBr Printer Python\n\n")
    if not resultado["sucesso"]:
        raise RuntimeError(resultado.get("mensagem", resultado.get("codigo")))
    dados = resultado["dados"]  # bytes; nenhum equipamento foi acessado
```

Para enviar pelo Windows, use uma chamada explícita:

```python
with criar_impressora({
    "modo": "escpos", "porta": r"\\localhost\elgin", "tipo": 0,
    "runtimeDirectory": "./runtime-local",
}) as impressora:
    # Descomente somente quando quiser enviar uma via física:
    # resultado = impressora.imprimir_texto("TESTE NAO FISCAL\n\n\n")
    pass
```

Execute Python e o worker no Windows para acessar uma porta UNC. O localhost
do WSL é outro ambiente. O cliente Linux recusa destinos Windows UNC.
`tipo: 0` é texto; `tipo: 8` é `ppEscPosStar`, a emulação validada no equipamento
Elgin do projeto. Não deduza a emulação pelo nome da impressora.
Tags exigem `interpretarTags: True`. Corte exige também `cortarPapel: True`,
cujo padrão é `False`. O componente não abre gaveta automaticamente.

## Spooler/FortesReport e DANFE

```python
from pathlib import Path
from acbr_printer import criar_impressora

xml = Path("nota.xml").read_bytes()
with criar_impressora(modo="spooler", impressora="ELGIN",
                     runtime_directory="./runtime-local") as impressora:
    print(impressora.listar_impressoras()["impressoras"])
    resultado = impressora.danfe_pdf(xml, {"larguraPapel": 72})
    if not resultado["sucesso"]:
        raise RuntimeError(resultado.get("mensagem", resultado.get("codigo")))
    with open("danfe.pdf", "xb") as output:
        output.write(resultado["pdf"])
    # Envio físico separado e explícito:
    # envio = impressora.imprimir_danfe(xml, {"copias": 1, "larguraPapel": 72})
```

O spooler recebe o nome da fila (`ELGIN`), enquanto o ESC/POS recebe a porta
(`\\localhost\elgin`). DANFE NFC-e modelo 65 pode usar ESC/POS ou Fortes;
NF-e modelo 55 usa Fortes/A4. PDF sempre usa Fortes e não inicia envio físico.
No driver de teste Elgin de 72 mm, `larguraPapel: 72` corrigiu cortes vistos
com 80 mm no cliente Node. Verifique a largura do driver da sua impressora.
Margens individuais ainda não fazem parte dessa API do motor.

O XML pode ser `str` UTF-8, `bytes`, `bytearray`, `memoryview` ou um mapping
com `xmlBase64`. Exemplo de integração opcional com um resultado fiscal:

```python
# ResultadoFiscal do emissor Python expõe a propriedade xml:
# if resultado_fiscal.xml is not None:
#     previa = impressora.danfe_pdf(resultado_fiscal.xml)
# Um resultado estrutural no formato comum também pode ser usado:
# previa = impressora.danfe_pdf({"xmlBase64": xml_base64_salvo})
```

O componente de impressão não assina, consulta ou transmite à SEFAZ, nem
confirma autorização fiscal. Use um processo `nfeProc` preservado quando quiser
imprimir o protocolo; não fabrique autorização para uma nota de produção.
Testes sintéticos com protocolo simulado devem permanecer identificados.

## API

Métodos síncronos: `capacidades`, `listar_impressoras`, `gerar_escpos`,
`imprimir_texto`, `danfe_pdf`, `imprimir_danfe`, `fechar`.
Aliases de migração: `criarImpressora`, `listarImpressoras`, `gerarEscpos`,
`imprimirTexto`, `danfePdf`, `imprimirDanfe`.

Resultados são `dict`, com os nomes do protocolo comum: `sucesso`, `estado`,
`envioIniciado`, `resultadoIncerto`, `codigo`, `mensagem`, `capacidades`,
`impressoras`. Geração acrescenta `dados`/`pdf` em `bytes` e os campos base64.
Estados: `PREPARADO`, `GERADO`, `ENVIADO`, `ERRO`.

| Configuração | Padrão / intervalo |
| --- | --- |
| `modo` | `escpos` ou `spooler`; padrão `escpos` |
| `porta`, `impressora` | Opcionais até o envio físico; o modo determina o destino |
| `tipo` | `0` ou `8`; padrão `0` |
| `colunas` | `48`, de 1 a 200 |
| `linhasEntreCupons` | `0`, de 0 a 100 |
| `interpretarTags`, `cortarPapel` | `False` |
| `runtimeDirectory` | Runtime local do projeto ou cache instalado explicitamente |
| `timeoutMs` | `30000`, de 1 a 120000 |
| `limiteFila` | `32`, de 0 a 1000 operações aguardando nesta instância |

Também são aceitas as grafias Python `linhas_entre_cupons`, `interpretar_tags`,
`cortar_papel`, `runtime_directory`, `timeout_ms` e `limite_fila`. Não informe
as duas grafias do mesmo campo. Opções DANFE: `copias` de 1 a 99 e
`larguraPapel` (ou `largura_papel`) de 40 a 300 milímetros, padrão 80.
Campos desconhecidos são rejeitados. Texto/XML têm limite de 2 MiB.

`ENVIADO` confirma entrega ao transporte, sem confirmar papel fisicamente
impresso. `ErroAcbrImpressora` expõe `codigo`, `resultado_incerto`,
`falha_limpeza` e `to_dict()`. Falhas retornadas pelo motor continuam resultados
com `sucesso: False`. Nenhuma operação é repetida automaticamente. Em resultado
incerto, confira a fila e o papel antes de tomar uma decisão de reimpressão.

Use `with` ou `fechar()` em `finally`. O fechamento cancela operações da
instância e aguarda sua limpeza. Instâncias do mesmo destino são serializadas
dentro de um processo Python; aplicações multiprocessos devem coordenar sua
própria fila. O timeout começa quando a operação entra no worker.

## Requisitos e validação

O runtime completo usa GTK2 no Linux e precisa das bibliotecas e de um display,
como desktop, WSLg ou Xvfb. Um display virtual não cria filas Windows.
O Windows usa o runtime x64 com suas DLLs distribuídas. Não há suporte validado
a macOS, ARM, Alpine/musl ou Python no navegador.

```sh
python -m unittest discover -s tests -v
python -m pip wheel --no-deps . --wheel-dir dist
```

A suíte padrão usa processos fictícios e nunca acessa impressoras ou SEFAZ.
Ela cobre protocolo, limites, validações, timeout, envio incerto, fechamento,
serialização por destino e instalação segura. O script `tests/native_offline.py`
exercita o worker real apenas com bytes/PDF e exige um runtime já instalado.
Os exemplos só enviam com `--enviar`; não os acrescente ao CI como impressão.

Consulte `docs/VALIDACAO.md` para o estado dos testes. Licença LGPL-2.1-or-later;
preserve `LICENSE`, `NOTICE`, fontes e avisos do runtime ao redistribuir.

## Estado da validação

Os testes físicos foram confirmados pelo usuário, incluindo códigos, corte e DANFE.
Houve uma ocorrência de falha do driver Elgin no spooler; o serviço foi restaurado
sem repetir trabalhos. Veja [o registro completo e a limitação de estabilidade](docs/VALIDACAO.md).
