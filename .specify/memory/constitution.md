# Constituição do Projeto — Bot Automático de Alertas de Vagas

Versão: 1.0.0 · Ratificada em: 2026-09-01

Este documento define os princípios inegociáveis do projeto. Toda decisão técnica nas fases
seguintes (planos, tarefas, código) deve ser compatível com estes artigos. Uma violação exige
justificativa explícita registrada em `research.md` ou no plano da feature correspondente.

## Artigo I — Simplicidade acima de tudo
O sistema resolve um problema pequeno e bem definido: coletar, deduplicar e notificar vagas.
Nenhuma abstração, framework, fila de mensageria, orquestrador externo ou camada extra deve ser
introduzida a menos que o escopo atual comprovadamente exija. SQL puro em vez de ORM; scripts
em vez de microsserviços; GitHub Actions em vez de infraestrutura dedicada.

## Artigo II — Idempotência e não-duplicação
Nenhuma vaga pode gerar mais de um alerta ao usuário. A checagem de duplicidade contra o banco
é uma etapa obrigatória do pipeline e não pode ser contornada por otimização ou conveniência.
A idempotência é garantida por uma chave de deduplicação estável (ver `data-model.md`), nunca
por heurísticas frágeis (ex.: comparar apenas o título).

## Artigo III — Banco de dados como fonte única da verdade sobre o que já foi notificado
O Neon Postgres é a única fonte confiável sobre quais vagas já foram vistas/notificadas.
Nenhum estado equivalente deve ser mantido em arquivos locais, variáveis de ambiente ou cache
efêmero do runner do GitHub Actions (que não persiste entre execuções).

## Artigo IV — Resiliência a falhas parciais
A falha de uma fonte de scraping (ex.: LinkedIn fora do ar, HTML mudou) não pode derrubar a
execução inteira. Cada scraper deve falhar isoladamente, logar o erro e permitir que as demais
etapas do pipeline (outras fontes, notificação de vagas já coletadas) prossigam.

## Artigo V — Segredos nunca em código
Credenciais (string de conexão do banco, token do Telegram) só existem como variáveis de
ambiente / GitHub Actions Secrets. Nenhum valor real é commitado, nem em exemplos — arquivos de
exemplo usam placeholders (`.env.example`).

## Artigo VI — Execução autônoma e observável
Como o sistema roda sem supervisão humana direta (cron a cada 3h), cada execução deve produzir
logs suficientes para diagnosticar, após o fato, quantas vagas foram coletadas, quantas eram
duplicadas, quantas foram notificadas e quais fontes falharam.

## Artigo VII — SQL explícito
Conforme stack definida, todo acesso ao banco é feito com `psycopg2` e SQL puro, escrito à mão.
Sem ORM, sem query builder. As queries vivem versionadas junto ao código, não geradas em tempo
de execução.

## Artigo VIII — Specs versionadas e imutáveis após implementação
Cada funcionalidade tem sua pasta numerada em `specs/NNN-nome-da-feature/`. Depois que uma spec
vira código, mudanças de comportamento exigem atualizar a spec correspondente antes (ou junto)
da mudança de código — a spec nunca fica desatualizada em relação ao sistema.

## Artigo IX — Teste no que é determinístico
Scraping de HTML de terceiros é frágil por natureza e não é 100% testável de forma automatizada
contínua. Ainda assim, tudo que é determinístico — normalização de dados, cálculo da chave de
deduplicação, filtragem por stack/localização/modalidade, montagem da mensagem do Telegram — deve
ter cobertura de teste antes de ser considerado pronto.
