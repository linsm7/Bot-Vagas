# Data Model: Bot Automático de Alertas de Vagas

Duas representações do mesmo conceito de domínio ("uma vaga elegível"):

1. **Contrato do scraper** — o dict Python padronizado que qualquer scraper de fonte (LinkedIn
   hoje, outras plataformas amanhã) deve produzir após a etapa de normalização.
2. **Schema do banco** — como esse dict é persistido no Neon Postgres, com as colunas extras que
   só existem no banco (chave primária, timestamps de controle).

O contrato formal (versão exaustiva, com tipos JSON Schema) está em
[`contracts/vaga-schema.md`](./contracts/vaga-schema.md) e
[`contracts/vaga.schema.json`](./contracts/vaga.schema.json). Este documento traz a visão
narrativa e a justificativa de cada campo.

## 1. Entidade: Vaga (saída da normalização, antes de tocar o banco)

| Campo | Tipo (Python) | Obrigatório | Descrição |
|---|---|---|---|
| `titulo` | `str` | Sim | Título da vaga como publicado, sem alterações. |
| `empresa` | `str` | Sim | Nome da empresa contratante, como exibido na listagem. |
| `localizacao` | `str` | Sim | Texto de localização como coletado (ex.: `"Brasília, DF, Brasil"`, `"Remoto"`). Não normalizado — cru da fonte. |
| `modalidade` | `str` (enum) | Sim | Um de `"remoto"`, `"presencial"`, `"hibrido"`. **Derivado** por `core/filters.py` a partir de `localizacao` + texto da vaga; nunca vem pronto da fonte. |
| `url` | `str` | Sim | Link direto para a vaga. Usado (normalizado) no cálculo de `hash_unico`. |
| `fonte` | `str` | Sim | Identificador curto e estável da plataforma de origem. Valor inicial: `"linkedin"`. |
| `descricao` | `str \| None` | Não | Trecho/corpo da descrição da vaga, se disponível na página de listagem sem custo extra de requisição. |
| `stack_detectada` | `list[str]` | Sim (pode ser lista vazia) | Subconjunto de `["react", "typescript", "python", "fullstack"]` detectado em título+descrição. Nunca `None` — lista vazia se nada detectado (mas nesse caso a vaga é descartada pelo filtro de elegibilidade, ver `spec.md` §4). |
| `data_publicacao` | `date \| None` | Não | Data de publicação da vaga, quando a fonte expõe de forma confiável. |
| `data_coleta` | `datetime` (UTC, ISO 8601) | Sim | Timestamp de quando o scraper coletou o dado. Gerado pelo código, não pela fonte. |
| `hash_unico` | `str` (64 hex chars) | Sim | `sha256(fonte + "|" + url_normalizada)`. Ver algoritmo abaixo. Calculado na normalização, não no banco. |

### Algoritmo de `url_normalizada` (para o cálculo de `hash_unico`)

1. Remover query string inteira (tudo após `?`) — elimina parâmetros de tracking/sessão do
   LinkedIn (`trk`, `refId`, `trackingId`, etc.).
2. Remover fragment (`#...`), se houver.
3. Remover barra final, se houver.
4. Resultado: `hash_unico = sha256(f"{fonte}|{url_normalizada}").hexdigest()`.

### Exemplo de dict produzido pela normalização

```python
{
    "titulo": "Desenvolvedor(a) Full Stack Pleno (React/Node)",
    "empresa": "Acme Tecnologia Ltda",
    "localizacao": "Brasília, Distrito Federal, Brasil",
    "modalidade": "presencial",
    "url": "https://www.linkedin.com/jobs/view/1234567890",
    "fonte": "linkedin",
    "descricao": "Buscamos dev full stack com experiência em React, TypeScript e Node.js...",
    "stack_detectada": ["react", "typescript", "fullstack"],
    "data_publicacao": "2026-08-30",
    "data_coleta": "2026-09-01T14:03:11+00:00",
    "hash_unico": "8f3a1c9e2b7d4f6a0e1c5b8a9d2f4e6c1b3a5d7f9e0c2b4a6d8f0e2c4b6a8d0f",
}
```

## 2. Regra de elegibilidade (aplicada ANTES da checagem de duplicidade)

Uma vaga só chega à etapa de checagem de duplicidade se, simultaneamente:
- `stack_detectada` não está vazia, **e**
- `modalidade == "remoto"` **ou** (`modalidade in ("presencial", "hibrido")` **e**
  `localizacao` contém Brasília/DF ou Goiânia/GO — incluindo região metropolitana, ex.:
  Águas Claras, Taguatinga, Aparecida de Goiânia).

Vagas que falham nesse filtro são descartadas em memória: **não** são persistidas, mesmo como
"vistas". Isso é intencional — se os critérios de filtro mudarem no futuro (ex.: adicionar
"Vue.js" à stack aceita), vagas antigas fora do critério antigo poderão ainda ser recuperadas nas
próximas varreduras, em vez de ficarem permanentemente marcadas como já processadas.

## 3. Schema do banco (Neon Postgres) — tabela `vagas`

> Especificação suficiente para gerar `init_db.sql` na Fase 1 sem ambiguidade. Este bloco **não**
> é um arquivo executável do repositório — é documentação.

```sql
CREATE TABLE vagas (
    id               BIGSERIAL PRIMARY KEY,
    hash_unico       CHAR(64)     NOT NULL,
    titulo           TEXT         NOT NULL,
    empresa          TEXT         NOT NULL,
    localizacao      TEXT         NOT NULL,
    modalidade       VARCHAR(20)  NOT NULL
                      CHECK (modalidade IN ('remoto', 'presencial', 'hibrido')),
    url              TEXT         NOT NULL,
    fonte            VARCHAR(50)  NOT NULL,
    descricao        TEXT,
    stack_detectada  TEXT[]       NOT NULL DEFAULT '{}',
    data_publicacao  DATE,
    data_coleta      TIMESTAMPTZ  NOT NULL,
    notificado_em    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_vagas_hash_unico UNIQUE (hash_unico)
);

CREATE INDEX idx_vagas_data_coleta ON vagas (data_coleta DESC);
CREATE INDEX idx_vagas_fonte       ON vagas (fonte);
```

### Justificativa das colunas que não vêm do dict do scraper

| Coluna | Motivo de existir só no banco |
|---|---|
| `id` | Chave primária técnica, sequencial. Nunca exposta fora do banco. |
| `notificado_em` | Timestamp de quando o `INSERT` aconteceu — que, pela ordem do pipeline (`plan.md` §3), coincide com "quando o Telegram confirmou o recebimento". Default `now()` porque o `INSERT` só roda depois do envio bem-sucedido. |

### Constraint de duplicidade

`UNIQUE (hash_unico)` é a única constraint de deduplicação. O pipeline faz um `SELECT` antes do
`INSERT` para decidir se notifica (ver `plan.md` §3), mas a constraint `UNIQUE` no banco é a
garantia final contra corrida/duplicidade (ex.: duas execuções do workflow sobrepostas por engano)
— um `INSERT ... ON CONFLICT (hash_unico) DO NOTHING` é o padrão de query recomendado para a
Fase 1, para que a etapa de persistência seja, ela mesma, idempotente.

### Por que `stack_detectada` é `TEXT[]` e não uma tabela normalizada `vaga_stack`

Viola-se conscientemente a 3ª forma normal aqui: o conjunto de valores possíveis de stack é
pequeno, fixo e definido em código (não pelo usuário), e não há necessidade de consulta
relacional complexa sobre ele nesta fase. Uma tabela associativa separada adicionaria um `JOIN`
sem benefício correspondente — decisão alinhada ao Artigo I (simplicidade) da constituição.

## 4. Mapeamento dict → colunas (para a query de `INSERT` da Fase 1)

| Campo do dict | Coluna | Transformação |
|---|---|---|
| `titulo` | `titulo` | Nenhuma |
| `empresa` | `empresa` | Nenhuma |
| `localizacao` | `localizacao` | Nenhuma |
| `modalidade` | `modalidade` | Nenhuma |
| `url` | `url` | Nenhuma (a URL crua é armazenada; só a versão normalizada é usada para o hash) |
| `fonte` | `fonte` | Nenhuma |
| `descricao` | `descricao` | Nenhuma (pode ser `NULL`) |
| `stack_detectada` | `stack_detectada` | `list[str]` → array Postgres |
| `data_publicacao` | `data_publicacao` | `str` ISO date → `DATE`, ou `NULL` |
| `data_coleta` | `data_coleta` | `datetime` → `TIMESTAMPTZ` |
| `hash_unico` | `hash_unico` | Nenhuma |
| _(nenhum — coluna gerada pelo banco)_ | `id` | `DEFAULT` (sequência) |
| _(nenhum — coluna gerada pelo banco)_ | `notificado_em` | `DEFAULT now()` |
