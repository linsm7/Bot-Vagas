# Research: Bot Automático de Alertas de Vagas

Registro das decisões técnicas tomadas nesta fase de planejamento e das alternativas
descartadas, com o motivo. Serve de referência para não reabrir debates já resolvidos sem um
motivo novo.

## 1. Chave de deduplicação: hash calculado vs. URL crua

**Decisão**: usar um hash SHA-256 calculado a partir de `fonte + url` (normalizados) como chave
única de deduplicação (`hash_unico`), em vez de usar a URL crua como chave.

**Alternativas consideradas**:
- *URL crua como chave única*: mais simples, mas URLs de listagem de vagas frequentemente
  carregam parâmetros de tracking/sessão (`?trk=...`, `?refId=...`) que variam entre a mesma
  vaga aparecendo em buscas diferentes — usar a URL crua causaria notificações duplicadas da
  mesma vaga.
- *Hash de título+empresa*: falha quando duas vagas diferentes da mesma empresa têm título
  idêntico (ex.: "Desenvolvedor Full Stack" postada duas vezes em datas diferentes) — geraria
  falsos positivos de duplicidade, escondendo vagas novas legítimas.

**Resultado**: hash sobre a URL *normalizada* (sem query string de tracking) combinada com a
fonte. Ver `data-model.md` para o algoritmo exato.

## 2. Formato de conexão com o Neon: `DATABASE_URL` único vs. variáveis separadas

**Decisão**: uma única variável de ambiente `DATABASE_URL` contendo a connection string completa
(`postgresql://user:pass@host/db?sslmode=require`), em vez de `PGHOST`/`PGUSER`/`PGPASSWORD`/
`PGDATABASE` separadas.

**Motivo**: é o formato que o painel do Neon já fornece pronto para copiar; reduz o número de
GitHub Actions Secrets a gerenciar de 4-5 para 1; `psycopg2.connect(dsn)` aceita a string
diretamente sem parsing manual.

## 3. Momento do registro no banco: antes ou depois do envio ao Telegram

**Decisão**: registrar no banco **depois** do envio confirmado ao Telegram (detalhado em
`plan.md`, seção 3).

**Alternativa considerada**: registrar assim que a vaga é considerada nova (antes de notificar),
o que simplificaria o código (não precisa propagar o resultado do envio até a etapa de
persistência). Rejeitada porque, em caso de falha no envio ao Telegram, a vaga ficaria marcada
como "vista" para sempre sem o usuário jamais ser notificado — viola diretamente o objetivo
central do sistema (Artigo II da constituição).

## 4. `stack_detectada`: coluna estruturada vs. inferência sob demanda

**Decisão**: persistir `stack_detectada` como `TEXT[]` (array Postgres) no momento da
normalização, em vez de re-derivar a stack a partir da descrição toda vez que for necessário.

**Motivo**: a descrição completa da vaga é opcional e pode não ser sempre armazenada/disponível;
gravar a stack já detectada no momento do scraping evita reprocessamento e permite consultas
futuras simples (ex.: "quantas vagas de React chegaram este mês") sem parsing de texto livre.

## 5. Fonte inicial: LinkedIn público, sem login

**Decisão**: iniciar exclusivamente pela busca pública de vagas do LinkedIn (a URL de busca que
não exige autenticação), conforme definido no contexto do projeto.

**Riscos aceitos** (não bloqueiam esta fase, mas documentados para a Fase 1):
- Bloqueio por rate-limit/anti-bot: mitigado operacionalmente por rodar apenas a cada 3h (baixa
  frequência) e por isolar falhas por fonte (Artigo IV) — não por técnicas de evasão de detecção.
- Estrutura de HTML sujeita a mudar sem aviso: mitigado por manter o parsing isolado em
  `scrapers/linkedin.py`, para que uma quebra afete só essa fonte.
- Está fora do escopo desta fase avaliar termos de uso da plataforma; é uma decisão de produto
  do usuário/Orquestrador, não uma decisão técnica desta spec.

## 6. Formato da mensagem Telegram: texto simples vs. HTML/Markdown

**Decisão**: usar `parse_mode: "HTML"` na API do Telegram, com o link da vaga como âncora
clicável no título.

**Motivo**: a API do Telegram suporta um subconjunto de HTML de forma mais previsível que
MarkdownV2 (que exige escapar muitos caracteres especiais e é uma fonte comum de bugs em textos
com caracteres como `.`, `-`, `(`, `)` — frequentes em nomes de empresas e títulos de vaga).

## 7. Granularidade da tabela: uma tabela única `vagas` vs. tabelas separadas por fonte

**Decisão**: uma única tabela `vagas`, com a coluna `fonte` identificando a origem, em vez de uma
tabela por plataforma (`vagas_linkedin`, `vagas_indeed`, ...).

**Motivo**: a checagem de duplicidade e a lógica de notificação são as mesmas independente da
fonte (Artigo I — simplicidade); múltiplas fontes futuras não mudam o formato do dado, só quem o
produz. Isso está alinhado ao contrato de dados agnóstico à fonte definido em `data-model.md`.
