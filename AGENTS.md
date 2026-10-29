# ACBr Printer Python

- Cliente independente de impressão. Não alterar os componentes fiscais nem exigir sua instalação.
- Reusar o motor local auditado ACBr Printer 0.1.2-local.1, protocolo 1/revisão ACBr 48590. Sem Delphi/ACBr Pro e sem dependência Node.js em execução. Instalação somente pelo arquivo local até existir release pública, sem fallback ao binário 0.1.1.
- Não imprimir, cortar papel nem abrir gaveta em testes automatizados. Os testes físicos pertencem ao pedido explícito do usuário e não devem ser repetidos após falha incerta.
- Não transmitir documentos ou consultar a SEFAZ. Exemplos fiscais são sintéticos e de homologação.
- Texto/XML somente pelo stdin do processo, sem shell; não registrar payloads, certificados ou segredos.
- ENVIADO confirma o transporte, sem confirmação física. Manter resultadoIncerto em timeout/falha após início possível do envio.
- Preservar licença, fontes correspondentes e todos os hashes do runtime. Não baixar binários automaticamente ao importar ou instalar o pacote.
- Testar o wheel instalado em consumidor externo. Não publicar nem criar repositório remoto enquanto o usuário prepara os repositórios.
