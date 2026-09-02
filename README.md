# Bot Automático de Alertas de Vagas

Bot autônomo em Python que varre plataformas de vagas periodicamente, filtra o que é relevante
para um perfil específico de desenvolvedor e avisa por Telegram assim que uma vaga nova aparece —
sem precisar abrir o LinkedIn (ou qualquer outro site) manualmente todo dia.

## O que é

Vagas boas somem da primeira página de busca em poucas horas, e checar múltiplas plataformas
manualmente várias vezes ao dia não escala. Este projeto automatiza essa varredura: roda sozinho
a cada 3 horas via GitHub Actions, coleta vagas de 4 fontes diferentes, aplica um conjunto de
critérios de elegibilidade (stack, localização, nível, recência, idioma) e envia uma mensagem no
Telegram só para as vagas novas que realmente atendem ao perfil configurado — sem duplicar alerta
para uma vaga já vista antes.

Os critérios (stack, localização, nível, exigência de inglês) hoje refletem um perfil específico
de desenvolvedor front-end/full stack, mas são simples de adaptar: vivem como constantes
versionadas em código (`core/filters.py`, `scrapers/*.py`), não como configuração externa — ver
[`specs/001-bot-alertas-vagas/contracts/environment-variables.md`](specs/001-bot-alertas-vagas/contracts/environment-variables.md)
para o porquê dessa escolha.

## Como funciona

```
GitHub Actions (cron a cada 3h)
        │
        ▼
1. Scraping ──────────► 4 fontes em paralelo lógico (LinkedIn, Gupy, Indeed, Empregare)
        │                cada fonte falha isolada — uma fora do ar não derruba as outras
        ▼
2. Normalização ──────► HTML/JSON bruto de cada fonte vira um dict padronizado
        │                (mesmo formato não importa a origem)
        ▼
3. Filtros ────────────► stack, localização/modalidade, nível, recência, idioma
        │                só sobrevive quem atende a TODOS os critérios
        ▼
4. Deduplicação ───────► consulta ao Postgres (Neon) por hash único da vaga
        │                vaga já vista antes é descartada aqui
        ▼
5. Notificação ────────► mensagem enviada ao Telegram
        │
        ▼
6. Registro ────────────► só grava no banco DEPOIS do envio confirmado
                          (garante que "registrado" == "usuário realmente recebeu")
```

Critérios de elegibilidade aplicados na etapa 3 (ver
[`specs/001-bot-alertas-vagas/spec.md`](specs/001-bot-alertas-vagas/spec.md) §4 para a versão
completa e as decisões registradas):

- **Cargo/stack**: título ou descrição menciona React, Next.js, TypeScript, Node.js, Angular ou
  caracteriza a vaga como Full Stack.
- **Localização/modalidade**: Remoto (desde que a vaga seja do Brasil — vaga remota de empresa/
  localização estrangeira é descartada) ou presencial/híbrido em Brasília (DF) ou Goiânia (GO),
  incluindo região metropolitana.
- **Nível**: Júnior ou Pleno. Sênior, Especialista, Staff, Lead e Principal são descartados.
- **Recência**: publicada nos últimos 7 dias.
- **Idioma**: descartada se a descrição exigir inglês avançado/fluente.
- **Novidade**: a vaga ainda não foi notificada antes (checagem por hash contra o banco).

### Fontes de vagas

| Fonte | Como é coletada | Observação |
|---|---|---|
| LinkedIn | Busca pública, sem login | — |
| Gupy | API pública que alimenta a busca agregada da plataforma | Descrição completa já vem na própria busca |
| Empregare | API pública que alimenta a busca do site | — |
| Indeed | Busca pública, sem login | O Indeed tem proteção anti-bot forte (Cloudflare) e costuma bloquear requisições automatizadas com HTTP 403 — esta fonte é melhor esforço: quando bloqueada, falha isolada (sem derrubar as outras 3) e simplesmente não contribui vagas naquela execução |

Nenhuma dessas fontes é oficialmente documentada/estável para este uso — são páginas e endpoints
públicos sujeitos a mudar sem aviso. Por isso o pipeline trata a falha de qualquer fonte como
esperada (loga e segue com as demais), em vez de depender de scraping de terceiros ser confiável.

## Stack técnica

- **Linguagem**: Python 3.11+
- **Scraping**: `requests` + `BeautifulSoup4` (HTML estático/JSON, sem headless browser)
- **Banco de dados**: PostgreSQL gerenciado pela [Neon](https://neon.tech), acessado com
  `psycopg2` e SQL puro (sem ORM)
- **Notificação**: Telegram Bot API via chamada HTTP direta (sem SDK)
- **Orquestração/agendamento**: GitHub Actions (cron + execução manual via `workflow_dispatch`)
- **Testes**: `unittest` (biblioteca padrão do Python)

## Como configurar do zero

Siga esta ordem — cada passo depende do anterior.

### 1. Clonar o repositório

```bash
git clone https://github.com/linsm7/Bot-Vagas.git
cd Bot-Vagas
```

### 2. Criar o banco (Neon Postgres)

1. Crie uma conta gratuita em [neon.tech](https://neon.tech) e um novo projeto.
2. Copie a *connection string* do projeto (formato
   `postgresql://usuario:senha@ep-xxxx.região.aws.neon.tech/nome_do_banco?sslmode=require`).
3. Rode o schema em `init_db.sql` contra esse banco — pelo SQL Editor do painel da Neon, ou via
   `psql`:
   ```bash
   psql "<sua connection string>" -f init_db.sql
   ```
   Isso cria a tabela `vagas` (ver
   [`specs/001-bot-alertas-vagas/data-model.md`](specs/001-bot-alertas-vagas/data-model.md) §3
   para o schema comentado).

### 3. Criar o bot do Telegram

1. Abra uma conversa com o [@BotFather](https://t.me/BotFather) no Telegram e crie um bot novo
   (`/newbot`). Guarde o **token** que ele devolve.
2. Envie qualquer mensagem para o seu bot recém-criado (ele precisa que você inicie a conversa
   antes de poder te enviar mensagens).
3. Descubra o seu **chat ID** acessando, no navegador:
   ```
   https://api.telegram.org/bot<SEU_TOKEN>/getUpdates
   ```
   e procurando o campo `"chat":{"id": ...}` na resposta JSON. Esse número (positivo para chat
   pessoal, negativo para grupo/canal) é o `TELEGRAM_CHAT_ID`.

### 4. Configurar os secrets no GitHub

No repositório, vá em **Settings → Secrets and variables → Actions → New repository secret** e
cadastre os três valores obrigatórios (sem aspas):

| Secret | Valor |
|---|---|
| `DATABASE_URL` | A connection string da Neon (passo 2) |
| `TELEGRAM_BOT_TOKEN` | O token do bot (passo 3) |
| `TELEGRAM_CHAT_ID` | O chat ID (passo 3) |

Contrato completo dessas variáveis (incluindo as opcionais) em
[`specs/001-bot-alertas-vagas/contracts/environment-variables.md`](specs/001-bot-alertas-vagas/contracts/environment-variables.md).

### 5. Testar manualmente

Com os secrets configurados, vá em **Actions → Coleta e notificação de vagas → Run workflow**
para disparar uma execução manual (via `workflow_dispatch`) sem esperar o cron. Confirme nos
logs da execução quantas vagas foram coletadas/filtradas/notificadas, e que a mensagem chegou no
Telegram.

### 6. Deixar rodando

Nada mais a fazer — o workflow `.github/workflows/cron.yml` já está agendado para rodar sozinho a
cada 3 horas (`0 */3 * * *`, UTC), sem intervenção manual.

## Rodando localmente

Útil para desenvolver ou depurar sem depender do GitHub Actions.

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edite .env com os mesmos 3 valores obrigatórios do passo 4 acima

python3 main.py
```

## Rodando os testes

```bash
python3 -m unittest discover -s tests -v
```

Cobre o que é determinístico do pipeline — normalização, cálculo de hash de deduplicação,
filtros de elegibilidade e parsing das respostas de cada fonte a partir de fixtures locais — sem
depender de rede real nem do banco. Scraping de HTML/API de terceiros não é 100% testável de
forma automatizada contínua (é validado manualmente); ver
[`.specify/memory/constitution.md`](.specify/memory/constitution.md) Artigo IX. Os mesmos testes
rodam automaticamente a cada push/PR via `.github/workflows/ci.yml`.

## Estrutura do projeto

```
Bot-Vagas/
├── .github/workflows/   # cron.yml (execução agendada) e ci.yml (testes em push/PR)
├── core/                # normalização, filtros de elegibilidade, banco, Telegram — agnóstico à fonte
├── scrapers/            # um módulo por fonte de vagas (linkedin, gupy, indeed, empregare) + contrato comum (base.py)
├── tests/               # testes automatizados (unittest)
├── specs/               # documentação técnica: requisitos, arquitetura, decisões, contratos de dados
├── init_db.sql          # schema do Postgres
├── main.py              # orquestra o pipeline fim a fim
└── .env.example         # variáveis de ambiente necessárias, com placeholders
```

## Documentação técnica detalhada

Este projeto segue [Spec-Driven Development](https://github.com/github/spec-kit): as decisões de
arquitetura, os critérios de negócio completos e o modelo de dados vivem versionados em
`specs/`, não só no código.

| Documento | Conteúdo |
|---|---|
| [`.specify/memory/constitution.md`](.specify/memory/constitution.md) | Princípios que governam todas as decisões técnicas do projeto |
| [`specs/001-bot-alertas-vagas/spec.md`](specs/001-bot-alertas-vagas/spec.md) | Requisitos, histórias de usuário, critérios de elegibilidade e de aceite |
| [`specs/001-bot-alertas-vagas/plan.md`](specs/001-bot-alertas-vagas/plan.md) | Arquitetura, stack, fluxo de execução, estrutura de pastas |
| [`specs/001-bot-alertas-vagas/research.md`](specs/001-bot-alertas-vagas/research.md) | Decisões técnicas e alternativas consideradas |
| [`specs/001-bot-alertas-vagas/data-model.md`](specs/001-bot-alertas-vagas/data-model.md) | Contrato do scraper e schema do banco |
| [`specs/001-bot-alertas-vagas/contracts/`](specs/001-bot-alertas-vagas/contracts/) | Contratos formais: schema da vaga, formato da mensagem do Telegram, variáveis de ambiente |
| [`specs/001-bot-alertas-vagas/quickstart.md`](specs/001-bot-alertas-vagas/quickstart.md) | Roteiro de validação manual ponta a ponta |
