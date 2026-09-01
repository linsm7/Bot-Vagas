# Contrato: Variáveis de Ambiente

Toda credencial/configuração externa ao código. Em produção (GitHub Actions), cada uma destas é
um **Repository Secret** injetado como variável de ambiente no step que roda `main.py` — nunca um
valor commitado. Localmente, um arquivo `.env` (não versionado) as fornece; `.env.example` (Fase 1)
documenta os nomes com valores placeholder.

## Obrigatórias

| Variável | Descrição | Exemplo/formato |
|---|---|---|
| `DATABASE_URL` | Connection string completa do Neon Postgres, incluindo SSL. | `postgresql://usuario:senha@ep-xxxx.us-east-2.aws.neon.tech/bot_vagas?sslmode=require` |
| `TELEGRAM_BOT_TOKEN` | Token do bot, obtido via [@BotFather](https://t.me/BotFather). | `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| `TELEGRAM_CHAT_ID` | ID numérico do chat/usuário/canal que deve receber os alertas. | `987654321` (positivo para chat pessoal, negativo para grupo) |

## Opcionais

| Variável | Descrição | Default se ausente |
|---|---|---|
| `LOG_LEVEL` | Verbosidade dos logs da execução. | `INFO` |
| `HTTP_USER_AGENT` | User-Agent enviado nas requisições de scraping. | Um User-Agent de navegador comum, definido em código |

## Explicitamente fora das variáveis de ambiente (decisão registrada)

Os termos de busca e a lista de cidades elegíveis (Brasília/Goiânia) **não** são variáveis de
ambiente — vivem como constantes versionadas em código (`core/filters.py`, Fase 1). Motivo:
mudar critério de negócio é uma mudança de comportamento do sistema, que deve passar por
atualização de código + spec (Artigo VIII da constituição), não por reconfiguração silenciosa via
secret, o que tornaria o comportamento do bot não seria rastreável no histórico do Git.

## Onde cada variável é usada

| Variável | Consumida por |
|---|---|
| `DATABASE_URL` | `core/database.py` — abre a conexão psycopg2 |
| `TELEGRAM_BOT_TOKEN` | `core/telegram.py` — monta a URL da API do Telegram |
| `TELEGRAM_CHAT_ID` | `core/telegram.py` — campo `chat_id` do payload (`contracts/telegram-message.md`) |
| `LOG_LEVEL` | `main.py` — configuração do logger no início da execução |
| `HTTP_USER_AGENT` | `scrapers/linkedin.py` (e futuros scrapers) — header das requisições |

## Configuração no GitHub Actions (referência para a Fase 1)

As três variáveis obrigatórias devem ser cadastradas em
**Settings → Secrets and variables → Actions → Repository secrets** do repositório, com os
mesmos nomes acima, e referenciadas no workflow como:

```yaml
env:
  DATABASE_URL: ${{ secrets.DATABASE_URL }}
  TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
  TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```

Este trecho é apenas ilustrativo desta documentação — a criação de `.github/workflows/cron.yml`
é escopo de uma fase de implementação futura.
