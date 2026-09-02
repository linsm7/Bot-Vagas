# Contrato: Dict Padronizado de Vaga

Este é o contrato de interface entre **qualquer scraper de fonte** e o resto do pipeline
(dedup, notificação, persistência). Todo scraper (hoje: `scrapers/linkedin.py`,
`scrapers/gupy.py`, `scrapers/indeed.py`, `scrapers/empregare.py` — contrato documentado em
`scrapers/base.py` — e qualquer `scrapers/*.py` futuro) deve produzir dicts que satisfaçam
exatamente este contrato após a etapa de normalização — o resto do sistema não sabe, e não deve
saber, de qual plataforma a vaga veio.

O schema formal, em JSON Schema (Draft 2020-12), está em [`vaga.schema.json`](./vaga.schema.json)
neste mesmo diretório e é a versão normativa. Esta página é a versão legível/anotada.

## Campos

| Campo | Tipo JSON | Obrigatório | Regras |
|---|---|---|---|
| `titulo` | `string` | Sim | `minLength: 1` |
| `empresa` | `string` | Sim | `minLength: 1` |
| `localizacao` | `string` | Sim | `minLength: 1` |
| `modalidade` | `string` | Sim | enum: `"remoto"`, `"presencial"`, `"hibrido"` |
| `url` | `string` | Sim | formato `uri`, deve começar com `https://` |
| `fonte` | `string` | Sim | `minLength: 1`, ex.: `"linkedin"` |
| `descricao` | `string \| null` | Não (default `null`) | — |
| `stack_detectada` | `array<string>` | Sim | itens dentre `["react", "nextjs", "typescript", "node", "angular", "fullstack"]`; pode ser `[]` |
| `data_publicacao` | `string \| null` | Não (default `null`) | formato `date` (`YYYY-MM-DD`) quando presente |
| `data_coleta` | `string` | Sim | formato `date-time` (ISO 8601, com timezone) |
| `hash_unico` | `string` | Sim | `pattern: "^[a-f0-9]{64}$"` (SHA-256 em hex minúsculo) |

## Compatibilidade

- Campos novos podem ser **adicionados** por um scraper futuro sem quebrar este contrato, desde
  que opcionais e ignorados pelo restante do pipeline até uma nova versão deste documento os
  formalizar.
- Nenhum campo listado acima pode ser removido ou ter seu tipo alterado sem uma nova versão desta
  spec (`002-...` ou uma revisão explícita desta, conforme Artigo VIII da constituição).
