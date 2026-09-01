# Tasks: Bot Automático de Alertas de Vagas

Quebra do `plan.md` em unidades de trabalho para a(s) próxima(s) fase(s) de implementação.
**Nenhuma destas tarefas foi executada nesta tarefa (Fase 0)** — este documento é apenas o
roteiro para quem implementar a seguir. Tarefas marcadas `[P]` são paralelizáveis entre si (sem
dependência direta).

## Fase 1.1 — Fundação de dados

- [ ] T001 Criar `init_db.sql` a partir do DDL em `data-model.md` §3
- [ ] T002 Provisionar o banco no Neon e aplicar `init_db.sql`
- [ ] T003 `[P]` Criar `.env.example` com os nomes de `contracts/environment-variables.md` (valores placeholder)
- [ ] T004 `[P]` Criar `requirements.txt` (`psycopg2-binary`, `requests`, `beautifulsoup4`, e libs de teste)

## Fase 1.2 — Núcleo determinístico (com testes, Artigo IX)

- [ ] T005 `core/normalizer.py`: HTML bruto de uma listagem → dict conforme `contracts/vaga-schema.md`
- [ ] T006 `core/filters.py`: implementa a regra de elegibilidade de `data-model.md` §2
- [ ] T007 `core/dedup.py`: implementa o algoritmo de `hash_unico` de `data-model.md` §1 (URL normalizada)
- [ ] T008 Testes unitários para T005–T007 (casos: vaga elegível, vaga fora de stack, vaga fora de localização, URLs com tracking params gerando o mesmo hash)

## Fase 1.3 — Integrações externas

- [ ] T009 `core/database.py`: conexão via `DATABASE_URL`, função de checagem de duplicidade, função de insert (`ON CONFLICT DO NOTHING`, conforme `data-model.md` §3)
- [ ] T010 `core/telegram.py`: monta e envia o payload de `contracts/telegram-message.md`, trata erro/rate-limit
- [ ] T011 `scrapers/base.py`: interface comum (contrato de entrada/saída de um scraper)
- [ ] T012 `scrapers/linkedin.py`: scraper da busca pública, produzindo dicts conforme o contrato

## Fase 1.4 — Orquestração e automação

- [ ] T013 `main.py`: implementa o pipeline de `plan.md` §3 fim a fim, com logging (Artigo VI)
- [ ] T014 `.github/workflows/cron.yml`: cron a cada 3h + `workflow_dispatch` para testes manuais
- [ ] T015 Cadastrar os Repository Secrets listados em `contracts/environment-variables.md`

## Fase 1.5 — Validação

- [ ] T016 Executar os 5 cenários de `quickstart.md` manualmente e registrar o resultado
- [ ] T017 Primeira execução real via GitHub Actions e confirmação de alerta recebido no Telegram

## Notas

- Esta lista é intencionalmente de alto nível — o grau de detalhe de cada tarefa (assinatura de
  função, nome exato de teste) é decisão de quem implementar, respeitando os contratos já fixados
  nesta fase.
- Qualquer desvio de um contrato definido em `specs/001-bot-alertas-vagas/` durante a
  implementação exige atualizar a spec correspondente primeiro (Artigo VIII), não silenciosamente
  divergir dela.
