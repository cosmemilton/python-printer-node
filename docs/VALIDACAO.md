# Validação local

Estado inicial do cliente Python 0.1.0 em 29/10/2026. Nenhuma publicação PyPI
ou criação de repositório remoto foi executada nesta etapa.

## Automatizado, sem hardware

- Windows Python 3.13: 19 casos, com 17 aprovados e dois casos específicos pulados
  (rejeição UNC Linux e criação de symlink sem permissão na conta Windows).
- Linux Python 3.12: todos os 19 casos passaram, incluindo symlink e recusa UNC.
- A suíte cobre protocolo JSONL fragmentado, UTF-8, ID/revisão, resposta duplicada,
  base64 canônico, estados, opções, XML e texto, orçamento de stdout/stderr,
  timeout com/sem envio possível, fechamento e fila por destino.
- Instalador: SHA256/tamanho antes de extrair, recusa sobrescrita, links e
  travessia; extração em staging e renomeação somente depois de todos os hashes.
- Motor real Windows e Linux/WSLg: capacidades, 879 bytes do cupom tipo 8 com
  14 comandos conferidos e SHA256 idêntico ao Node, PDFs dos modelos 55/65 e
  DANFE NFC-e em arquivo passaram, sem equipamento físico.
- Instalador com tarball original auditado: extração offline Windows e consulta
  de capacidades do runtime extraído passaram; sem dependência Node.js.

O script `tests/native_offline.py` cobre o cupom tipo 8 com os 14 comandos
esperados, corte opt-in único, bytes idênticos ao cliente Node, PDFs dos modelos
55/65 e DANFE NFC-e para porta FILE. Ele não abre fila nem envia ao hardware.
Os XMLs em `tests/fixtures` são sintéticos e em homologação, com protocolo
explicitamente simulado quando presente; não houve transmissão à SEFAZ.

## Runtime local corrigido

O bundle final fixado é `acbr-printer-runtime-0.1.2-local.1.tgz`, com
71.442.624 bytes e SHA256
`0aba5fb78b40099427a74076a70d4e8edcda3b8fa243a0f31a5db5c8d2e64093`.
Ele inclui a correção do JobTitle do relatório de texto FortesReport e as fontes
correspondentes. A instalação remota está desabilitada: sem `--arquivo`, a CLI
retorna `RUNTIME_LOCAL_NAO_PUBLICADO` e não cria destino nem acessa a rede.

A instalação offline real desse bundle no Linux passou, assim como os testes
nativos do runtime extraído: 879 bytes avançados conferidos contra Node,
PDFs de NFC-e e NF-e e DANFE NFC-e para arquivo. A tarefa principal executa a
instalação externa Windows e os testes físicos, registrando seu resultado.

## Impressora real confirmada em 29/10/2026

O usuário confirmou os cinco testes de cada linguagem na fila Windows `ELGIN`,
driver `ELGIN i9(USB)`, porta USB001 e compartilhamento `\\localhost\elgin`:

| Teste | Confirmação do usuário |
| --- | --- |
| Texto tipo 0 | Legível |
| Tipo 8: negrito, sublinhado, fontes e alinhamentos | Corretos |
| QR Code, Code128, EAN-13 e corte total | Códigos lidos e corte correto |
| Texto gráfico com FortesReport | Legível e completo |
| DANFE NFC-e por ESC/POS tipo 8 | Correto |
| DANFE NFC-e por FortesReport/spooler | Correto, `larguraPapel: 72` |

Foi enviada uma única via de cada teste. Uma primeira tentativa de texto Fortes
em PHP falhou antes de `envioIniciado`; após corrigir o JobTitle no motor local,
essa etapa foi executada e confirmada. Os trabalhos bem-sucedidos não foram
repetidos. Não houve abertura de gaveta nem beep.

O XML da NFC-e é sintético, modelo 65/ambiente 2, R$ 10,00, com protocolo 100
explicitamente simulado. Os testes não transmitiram documentos à SEFAZ nem
usaram certificados reais. O XML modelo 55 foi usado somente para PDF offline.

## Ocorrência do driver e recuperação

Apesar da saída correta no papel, o Windows registrou falhas de `spoolsv.exe`
no módulo `DrvRender_x64_ELGIN.dll` após a sequência de testes gráficos. A causa
exata dentro da DLL fechada não foi comprovada. A impressão de texto usa um
formato curto customizado no Fortes; isso é diferente do formulário 72 x 297 mm
do driver, mas não comprova, por si só, a causa da falha.

Com autorização do usuário e elevação de administrador, foram identificados
três trabalhos sintéticos já confirmados, por nomes, horários e SHA256 do RAW.
Seus arquivos foram preservados em quarentena, e o spooler foi restaurado com
a fila vazia. Não houve reenvio durante a recuperação. O serviço permaneceu
ativo nas verificações finais e os testes offline voltaram a passar.

A estabilidade do driver Elgin em sequências gráficas continua uma limitação
observada; papel legível e `ENVIADO` não são prova dessa estabilidade. O SDK
não altera drivers ou configurações globais e não repete trabalhos após erro.

## Instalação e execução externas

- PHP: instalado com Composer em consumidor separado, sem symlinks e sem scripts.
- Python: wheel instalado em ambiente virtual separado.
- Ambos executaram o motor sem Node.js no PATH e geraram PDFs 55/65.
- Os comandos avançados ficaram byte a byte iguais aos gerados pelo Node.
- Os runtimes Windows/Linux foram verificados por inventário e SHA256, com fontes,
  patch, licenças e receita de reconstrução preservados.
- Coexistência conferida com `cosmemilton/acbr-php:0.1.0-alpha2` e
  `acbr-python==0.1.0a5`, sem colisões de autoload/import e sem iniciar operação fiscal.
- Testes negativos adicionais no Windows: 13 por cliente, com JSON/UTF-8 inválidos,
  limites de saída, timeout, ID/revisão, duplicação e limpeza; nenhum processo órfão.

## Distribuição local

Cliente `0.1.0`; runtime `0.1.2-local.1`. O bundle tem 71.442.624 bytes e SHA256
`0aba5fb78b40099427a74076a70d4e8edcda3b8fa243a0f31a5db5c8d2e64093`.
O instalador exige arquivo local e não acessa uma URL ainda inexistente.
Nenhum repositório remoto foi criado e nenhum pacote foi publicado nesta etapa.
