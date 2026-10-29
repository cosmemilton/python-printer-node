# Motor compartilhado de impressão

O arquivo `runtime.lock.json` fixa o bundle local `0.1.2-local.1`. O consumidor executa diretamente Free Pascal/Lazarus, sem Node.js, Delphi ou ACBr Pro.

A origem é o motor de `cosmemilton-acbr-printer-node@0.1.1` (fontes no commit `619d05eec71564bb7343b4cdb7f275cdd83947bb`), com o patch local desta pasta. Ele define o título do relatório de texto Fortes, evitando o acesso a um Owner ausente durante a preparação. O pacote Node publicado não foi modificado.

Cada runtime preserva em `sources/driver-source.tar.gz` os fontes correspondentes, locks, licenças e receita de reconstrução, além dos fontes ACBr/Fortes. O bundle ainda não possui uma URL de release: instale explicitamente com o arquivo local, conforme o README. Não substitua o pin por um download sem auditoria.
