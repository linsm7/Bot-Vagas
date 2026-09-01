# Bot Automático de Alertas de Vagas

Sistema autônomo em Python que varre plataformas de emprego periodicamente, filtra vagas de
Desenvolvedor (React, Next.js, TypeScript, Node.js, Angular, Full Stack) Remoto ou presencial em
Brasília/Goiânia, de nível Júnior/Pleno, recentes e sem exigência de inglês, e envia alertas via
Telegram.

Este repositório segue a metodologia [GitHub Spec Kit](https://github.com/github/spec-kit)
(Spec-Driven Development): a documentação em `.specify/` e `specs/` é a fonte da verdade e
antecede qualquer código de produção.

## Como navegar nesta documentação

| Documento | Conteúdo |
|---|---|
| [`.specify/memory/constitution.md`](.specify/memory/constitution.md) | Princípios que governam todas as decisões técnicas do projeto |
| [`specs/001-bot-alertas-vagas/spec.md`](specs/001-bot-alertas-vagas/spec.md) | O quê e por quê: requisitos, histórias de usuário, critérios de aceite |
| [`specs/001-bot-alertas-vagas/plan.md`](specs/001-bot-alertas-vagas/plan.md) | Arquitetura, stack, fluxo de execução, estrutura de pastas planejada |
| [`specs/001-bot-alertas-vagas/research.md`](specs/001-bot-alertas-vagas/research.md) | Decisões técnicas e alternativas consideradas |
| [`specs/001-bot-alertas-vagas/data-model.md`](specs/001-bot-alertas-vagas/data-model.md) | Modelo de dados: contrato do scraper e schema do banco (Neon Postgres) |
| [`specs/001-bot-alertas-vagas/contracts/`](specs/001-bot-alertas-vagas/contracts/) | Contratos formais: schema JSON da vaga, formato da mensagem Telegram, variáveis de ambiente |
| [`specs/001-bot-alertas-vagas/quickstart.md`](specs/001-bot-alertas-vagas/quickstart.md) | Cenário de validação ponta a ponta para quando o sistema estiver implementado |
| [`specs/001-bot-alertas-vagas/tasks.md`](specs/001-bot-alertas-vagas/tasks.md) | Quebra de tarefas para as próximas fases de implementação |

## Status

**Fase 0 — Planejamento (concluída nesta tarefa).** Nenhum código de produção existe ainda.
A implementação (scrapers, `core/`, `main.py`, `init_db.sql`, workflow do GitHub Actions) é
escopo das fases seguintes, guiada por estes documentos.
