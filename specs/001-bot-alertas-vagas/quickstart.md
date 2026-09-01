# Quickstart: Validação Ponta a Ponta

Este documento **não** é executável hoje — nenhum código existe ainda (Fase 0). Ele define o
roteiro de validação manual que deve ser seguido assim que a Fase 1 (implementação) entregar o
pipeline, para confirmar que o sistema implementado cumpre os critérios de aceite de `spec.md` §7.

## Pré-requisitos para rodar este roteiro (quando aplicável)

1. Banco Neon provisionado, com `init_db.sql` aplicado (tabela `vagas` criada conforme
   `data-model.md`).
2. Bot do Telegram criado via BotFather, com o usuário já tendo iniciado conversa com ele.
3. Variáveis de ambiente configuradas conforme `contracts/environment-variables.md`.

## Cenário 1 — Vaga nova elegível gera alerta

1. Rodar `python main.py` manualmente (fora do cron, para teste).
2. Confirmar no log que ao menos uma vaga foi coletada do LinkedIn.
3. Para uma vaga que atenda aos critérios de `spec.md` §4, confirmar:
   - Uma mensagem chegou no Telegram configurado, com o formato de `contracts/telegram-message.md`.
   - Uma linha correspondente existe em `SELECT * FROM vagas WHERE hash_unico = '<hash da vaga>'`.

## Cenário 2 — Vaga já notificada não duplica

1. Rodar `python main.py` uma segunda vez, imediatamente após o Cenário 1, sem alterar o banco.
2. Confirmar que **nenhuma** nova mensagem chega no Telegram referente à mesma vaga do Cenário 1.
3. Confirmar que a contagem de linhas em `vagas` para aquele `hash_unico` continua sendo 1
   (constraint `UNIQUE` não gerou erro nem duplicata).

## Cenário 3 — Falha de uma fonte não derruba o pipeline

1. Simular indisponibilidade da fonte (ex.: apontar temporariamente a URL de busca do LinkedIn
   para um endpoint inválido, ou interceptar a requisição para forçar erro).
2. Rodar `python main.py`.
3. Confirmar no log que o erro da fonte foi registrado, mas o processo terminou com código de
   saída de sucesso (ou, se houver mais de uma fonte configurada, que as demais fontes foram
   processadas normalmente).

## Cenário 4 — Vaga fora do critério não é persistida nem notificada

1. Usar (ou simular) uma vaga que não atenda a um dos critérios de `spec.md` §4 (ex.: vaga de
   "Designer UX" remoto).
2. Rodar `python main.py`.
3. Confirmar que nenhuma mensagem sobre essa vaga chega no Telegram e que nenhuma linha
   correspondente é inserida em `vagas`.

## Cenário 5 — Execução agendada via GitHub Actions

1. Confirmar que o workflow `.github/workflows/cron.yml` está habilitado no repositório.
2. Aguardar (ou disparar manualmente via `workflow_dispatch`, se configurado) uma execução.
3. Confirmar no painel "Actions" do GitHub que a execução terminou com sucesso e que os logs são
   suficientes para responder: quantas vagas foram coletadas, quantas eram duplicadas, quantas
   foram notificadas (Artigo VI da constituição).
