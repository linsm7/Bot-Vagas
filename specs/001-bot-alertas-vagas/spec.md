# Feature Spec: Bot Automático de Alertas de Vagas

**Branch/Feature**: `001-bot-alertas-vagas` · **Status**: Rascunho aprovado para planejamento
**Entrada**: Descrição funcional fornecida pelo Orquestrador (ver contexto do projeto)

## 1. Resumo

Um sistema autônomo que, periodicamente e sem intervenção humana, descobre vagas de emprego
relevantes para um perfil de Desenvolvedor (React, Next.js, TypeScript, Node.js, Angular, Full
Stack) publicadas como Remoto ou como presencial em Brasília/Goiânia, de nível Júnior ou Pleno,
publicadas recentemente e sem exigência de inglês, e avisa o usuário via Telegram assim que uma
vaga nova (nunca vista antes) é encontrada.

## 2. Motivação (Por quê)

Vagas relevantes somem da primeira página de resultados em horas e a busca manual e repetida em
múltiplas plataformas é uma tarefa tediosa e fácil de negligenciar. Automatizar a varredura
garante que o usuário saiba de uma vaga nova em minutos/poucas horas após a publicação, sem
precisar checar manualmente.

## 3. Usuário e histórias

**Persona única**: o candidato (usuário do bot), que também é o operador do repositório.

- **História 1**: Como candidato, quero receber uma mensagem no Telegram assim que uma vaga
  compatível com meu perfil for publicada, para poder me candidatar rapidamente.
- **História 2**: Como candidato, não quero receber a mesma vaga duas vezes, mesmo que o bot
  rode várias vezes ao dia e a vaga continue aparecendo nos resultados de busca.
- **História 3**: Como candidato, quero que o sistema rode sozinho (GitHub Actions), sem que eu
  precise executar nada manualmente ou manter uma máquina ligada.
- **História 4**: Como candidato, quero que uma falha temporária de uma fonte de vagas (ex.:
  LinkedIn bloqueando a requisição) não impeça que eu continue recebendo alertas de outras
  fontes ou nas próximas execuções.

## 4. Critérios de relevância de uma vaga (regras de negócio)

Uma vaga é elegível para notificação somente se, cumulativamente:

1. **Cargo**: o título/descrição indica uma posição de desenvolvimento de software (ex.: contém
   termos como "Desenvolvedor", "Developer", "Engenheiro de Software", "Programador" — a lista
   exata de termos-gatilho e suas variações é um detalhe de implementação, não desta spec).
2. **Stack**: o título ou a descrição menciona ao menos uma de: React, Next.js, TypeScript,
   Node.js, Angular, ou caracteriza a vaga como Full Stack. (Stack alinhada ao perfil real do
   usuário — linkedin.com/in/linsm7 —, que substituiu o conjunto anterior, `{React, TypeScript,
   Python, Full Stack}`; Python foi removido por não constar em nenhuma parte do perfil.)
3. **Localização/modalidade**, uma das duas:
   - Remoto (sem exigência de presença física em nenhuma cidade específica); OU
   - Presencial/híbrido em Brasília (DF) ou Goiânia (GO) — incluindo região metropolitana.
4. **Recência**: `data_publicacao` está dentro dos últimos 7 dias em relação ao momento da
   execução do pipeline. **Decisão registrada**: quando `data_publicacao` é desconhecida (`None`
   — comum, pois o card de busca do LinkedIn nem sempre expõe uma data parseável), a vaga **não**
   é descartada por este critério; tratar ausência de dado como "vaga antiga" descartaria vagas
   legítimas e recentes só porque o LinkedIn não anotou a data no card, o mesmo tipo de perda que
   o critério de modalidade (item 3) já evita para localizações ambíguas.
5. **Novidade**: a vaga ainda não está registrada como já notificada no banco de dados (ver
   `data-model.md` para a chave de deduplicação).
6. **Nível**: a vaga é de nível Júnior ou Pleno — vagas de nível Sênior, Especialista, Staff,
   Lead ou Principal são descartadas. **Decisão registrada**: quando a vaga não tem nenhum sinal
   textual de nível (nem júnior/pleno, nem sênior/especialista), ela é **aceita por padrão**;
   muitas vagas júnior/pleno legítimas não anotam o nível explicitamente, e descartar por falta
   de prova perderia vagas relevantes de verdade.
7. **Inglês não exigido**: a vaga é descartada se a descrição completa mencionar exigência de
   inglês avançado/fluente (ex.: "inglês avançado", "inglês fluente", "advanced English",
   "fluent in English", "necessário inglês" — lista não exaustiva, pode ser ampliada com bom
   senso). Ausência de qualquer menção ao idioma na descrição é tratada como elegível — não se
   exige menção explícita de que o inglês não é necessário.

Vagas que não atendem a todos os critérios acima são descartadas silenciosamente (não geram
notificação, não são persistidas).

### 4.1 Nota de implementação: ordem das checagens e custo de rede

Os critérios 6 e 7 dependem da descrição completa da vaga, que os cards de busca do LinkedIn não
trazem (só título/empresa/localização) — verificá-los exige uma requisição HTTP adicional por
vaga candidata (buscar a página individual). Para não gastar essa requisição à toa, a
implementação (`main.py::executar_pipeline`) só busca a descrição completa de uma vaga depois que
ela já passou pelos critérios 1-4 (mais baratos, sem requisição extra) **e** pelo critério 5
(novidade, checagem no banco por hash — também não depende de descrição). Uma falha de rede ou de
parsing ao buscar a descrição completa (`scrapers/linkedin.py::buscar_descricao_completa`) faz a
vaga ser descartada *nesta* execução (ela é reprocessada na próxima, pois só é persistida no banco
depois de notificada — ver item 5 e `data-model.md` §3).

## 5. Escopo desta fase (Fase 0)

Esta spec, e os documentos irmãos em `specs/001-bot-alertas-vagas/`, cobrem **somente**
planejamento e arquitetura. Não há código de produção associado a esta feature ainda. A
plataforma de scraping inicial é o LinkedIn (busca pública, sem login). Outras plataformas
podem ser adicionadas em iterações futuras — o contrato de dados definido aqui (`data-model.md`)
foi desenhado para ser agnóstico à fonte, exatamente para permitir isso sem quebrar o schema.

## 6. Fora de escopo (explicitamente)

- Interface web, dashboard ou qualquer forma de interação além do Telegram.
- Candidatura automática às vagas.
- Autenticação/login em plataformas de vagas (o scraping inicial usa apenas páginas públicas).
- Múltiplos usuários/destinatários (o sistema assume um único chat/destino do Telegram).
- Machine learning ou scoring de relevância além dos critérios booleanos da seção 4.

## 7. Critérios de aceite da feature (comportamento observável, quando implementada)

- [ ] Dada uma vaga nova compatível com os critérios da seção 4, o usuário recebe uma mensagem
      no Telegram contendo, no mínimo: título, empresa, localização/modalidade e link para a vaga.
- [ ] Dada uma vaga já notificada anteriormente, executar o pipeline novamente **não** gera uma
      segunda mensagem para essa vaga.
- [ ] Dado que uma fonte de scraping falha (erro de rede, bloqueio, mudança de HTML), a execução
      é registrada em log com erro, mas o pipeline continua e processa as demais fontes/etapas.
- [ ] Dada uma vaga que não atende a um dos critérios da seção 4 (ex.: vaga de Designer), ela não
      gera notificação nem é persistida no banco.
- [ ] O pipeline completo roda de ponta a ponta via GitHub Actions em um cron a cada 3 horas, sem
      intervenção manual.

## 8. Dependências e restrições conhecidas

- Scraping de páginas públicas do LinkedIn está sujeito a bloqueios/CAPTCHAs e mudanças de
  markup sem aviso prévio — tratado como risco aceito nesta fase (mitigação: Artigo IV da
  constituição — falha isolada por fonte).
- A verificação dos critérios 6 e 7 da seção 4 (nível, inglês) exige uma requisição HTTP adicional
  por vaga candidata, para buscar a página individual da vaga (o card de busca não traz a
  descrição completa). Isso torna a execução mais lenta e aumenta o número de requisições ao
  LinkedIn por execução — risco aceito explicitamente pelo usuário em troca de uma checagem real
  de nível/inglês em vez de uma heurística só por título (ver §4.1).
- O Telegram exige que o usuário tenha iniciado conversa com o bot (ou o bot esteja no
  grupo/canal) para poder enviar mensagens — pré-requisito operacional, não técnico.
- GitHub Actions cron não garante execução no minuto exato agendado (pode atrasar em períodos de
  alta demanda da plataforma) — aceitável dado que o objetivo é "minutos/poucas horas", não tempo
  real.

## 9. Decisões registradas nesta spec

Nenhuma ambiguidade bloqueante foi encontrada na etapa inicial (Fase 0). Decisões de
nomenclatura de campos, schema e variáveis de ambiente estão registradas em `data-model.md`,
`research.md` e no relatório final ao Orquestrador (seção DECISÕES).

Decisões tomadas durante a implementação dos critérios 4, 6 e 7 da seção 4 (todas também
comentadas no código correspondente):

- **Stack**: substituição de `{React, TypeScript, Python, Full Stack}` por `{React, Next.js,
  TypeScript, Node.js, Angular, Full Stack}`, com base no perfil real do usuário no LinkedIn
  (competências curadas: Next.js, React.js, TypeScript, Node.js, Angular). Python removido por
  falta de qualquer evidência no perfil.
- **Recência com `data_publicacao` ausente**: aceitar (não descartar) — ver justificativa no
  item 4 acima.
- **Nível sem sinal textual**: aceitar por padrão — ver justificativa no item 6 acima.
- **Ordem das checagens de nível/inglês**: adiadas para depois dos critérios 1-5 (mais baratos)
  para minimizar requisições extras ao LinkedIn — ver §4.1.
- **`vaga.schema.json` / `vaga-schema.md`**: o enum de `stack_detectada` foi atualizado junto
  (não estava na lista de arquivos citados na tarefa, mas é o contrato formal que a mudança de
  stack afeta diretamente).
