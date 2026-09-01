# Implementation Plan: Bot Automático de Alertas de Vagas

**Spec de origem**: [`spec.md`](./spec.md) · **Constituição**: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)

## 1. Contexto técnico

| Item | Valor |
|---|---|
| Linguagem | Python 3.11+ |
| Banco de dados | PostgreSQL gerenciado pela Neon |
| Driver de banco | `psycopg2`, SQL puro (sem ORM — Artigo VII) |
| Scraping | `requests` + `BeautifulSoup4`, HTML estático (sem headless browser nesta fase) |
| Notificação | Telegram Bot API via `requests` (chamada HTTP direta, sem SDK) |
| Orquestração/agendamento | GitHub Actions, cron a cada 3 horas |
| Fonte de scraping inicial | LinkedIn — busca pública de vagas (sem autenticação) |

## 2. Gate de simplicidade (Artigo I)

- Sem fila de mensageria: o volume esperado (varredura a cada 3h, poucas dezenas de vagas por
  execução) não justifica Celery/SQS/etc. Processamento síncrono e sequencial é suficiente.
- Sem ORM: confirma Artigo VII: `psycopg2` com SQL parametrizado.
- Sem servidor: o processo é um script que roda, termina e o runner do GitHub Actions é
  descartado. Não há estado em memória entre execuções — todo estado persistente vive no Neon.
- Sem framework de scraping (Scrapy, Playwright) nesta fase: página pública do LinkedIn é
  renderizada em HTML estático o suficiente para `requests` + `BeautifulSoup4`. Se uma fonte
  futura exigir JS, isso é reavaliado nessa fonte especificamente — não adotado preventivamente
  para todas.

## 3. Fluxo de execução (pipeline)

```
┌────────────────────┐
│ GitHub Actions cron │  a cada 3h (ex.: "0 */3 * * *", UTC)
└─────────┬───────────┘
          │ dispara job
          ▼
┌────────────────────────────┐
│ 1. Scraping                │  por fonte (inicia com LinkedIn público)
│    - busca por vaga        │  cada fonte roda isolada (Artigo IV):
│    - extrai HTML bruto     │  exceção em uma fonte não interrompe as demais
└─────────┬───────────────────┘
          ▼
┌────────────────────────────┐
│ 2. Normalização             │  HTML bruto → dict padronizado
│    - aplica filtro de       │  (ver contracts/vaga-schema.md)
│      cargo/stack/localização│  vagas fora do critério são descartadas aqui
│    - calcula hash_unico     │  (chave de deduplicação)
└─────────┬───────────────────┘
          ▼
┌────────────────────────────┐
│ 3. Checagem de duplicidade  │  SELECT 1 FROM vagas WHERE hash_unico = %s
│    (consulta ao Neon)       │  se já existe → descarta, não notifica de novo
└─────────┬───────────────────┘
          │ vaga é nova
          ▼
┌────────────────────────────┐
│ 4. Envio de alerta Telegram │  1 mensagem por vaga nova
│    (ver contracts/          │  se o envio falhar, a vaga NÃO é registrada
│     telegram-message.md)    │  (será re-tentada na próxima execução — Artigo II/III)
└─────────┬───────────────────┘
          │ envio confirmado (HTTP 200 da API do Telegram)
          ▼
┌────────────────────────────┐
│ 5. Registro no banco        │  INSERT INTO vagas (...)
│    (Neon Postgres)          │  é isso que marca a vaga como "já notificada"
└──────────────────────────────┘
```

**Decisão de ordenação (registrada)**: o registro no banco acontece *depois* do envio bem-sucedido
ao Telegram, não antes. Isso significa que a existência de uma linha na tabela `vagas` é, por
definição, prova de que o usuário foi notificado. Se o envio ao Telegram falhar, a vaga não é
persistida e será reprocessada (e reenviada) na próxima execução do cron — evitando o cenário
inverso, mais grave, de "vaga marcada como notificada mas o usuário nunca recebeu a mensagem".
Motivo: o Artigo II (nenhuma vaga sem notificação real) pesa mais que o risco de, em uma falha
rara entre envio e registro, reenviar a mesma vaga uma vez a mais.

## 4. Estrutura de pastas planejada para a implementação (Fases futuras — NÃO criada nesta tarefa)

```
Bot-Vagas/
├── .github/
│   └── workflows/
│       └── cron.yml            # cron trigger, chama main.py
├── core/
│   ├── database.py             # conexão psycopg2, funções de consulta/insert
│   ├── dedup.py                # cálculo de hash_unico, checagem de duplicidade
│   ├── normalizer.py           # HTML bruto -> dict padronizado (contrato da vaga)
│   ├── filters.py              # regras de elegibilidade (cargo/stack/localização)
│   └── telegram.py             # integração com a API do Telegram
├── scrapers/
│   ├── base.py                 # interface comum a todo scraper de fonte
│   └── linkedin.py             # scraper da busca pública do LinkedIn
├── main.py                     # orquestra o pipeline fim a fim (seção 3)
├── init_db.sql                 # DDL gerado a partir de data-model.md (Fase 1)
├── requirements.txt
└── .env.example
```

Esta árvore é **especificação**, não implementação — nenhum desses arquivos foi criado nesta
tarefa. Ela existe aqui para que a Fase 1 (implementação) não precise redecidir a organização do
projeto.

## 5. Documentos de apoio gerados junto com este plano

| Documento | Cobre |
|---|---|
| [`research.md`](./research.md) | Alternativas consideradas e por que foram descartadas |
| [`data-model.md`](./data-model.md) | Contrato do dict padronizado da vaga + schema do banco |
| [`contracts/vaga-schema.md`](./contracts/vaga-schema.md) + [`contracts/vaga.schema.json`](./contracts/vaga.schema.json) | Contrato formal do dict/JSON da vaga |
| [`contracts/telegram-message.md`](./contracts/telegram-message.md) | Formato exato da mensagem enviada |
| [`contracts/environment-variables.md`](./contracts/environment-variables.md) | Toda variável de ambiente/secret necessária |
| [`quickstart.md`](./quickstart.md) | Cenário de validação manual ponta a ponta |
| [`tasks.md`](./tasks.md) | Quebra de tarefas para a Fase 1 (implementação) |

## 6. Rastreamento de complexidade (exceções à constituição)

Nenhuma exceção aos Artigos I–IX foi necessária nesta fase. Tabela vazia intencionalmente —
deve ser preenchida em planos futuros apenas se uma decisão violar algum artigo e for
conscientemente aceita.

| Violação | Por que foi necessária | Alternativa mais simples rejeitada porque |
|---|---|---|
| _(nenhuma)_ | — | — |
