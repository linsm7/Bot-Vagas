# Contrato: Mensagem de Alerta no Telegram

Define exatamente o que é enviado à API do Telegram (`POST https://api.telegram.org/bot<TOKEN>/sendMessage`)
para cada vaga nova, uma chamada por vaga.

## Payload da requisição

```json
{
  "chat_id": "<TELEGRAM_CHAT_ID>",
  "text": "<ver template abaixo>",
  "parse_mode": "HTML",
  "disable_web_page_preview": false
}
```

- `disable_web_page_preview: false` é deliberado: a pré-visualização do link ajuda a reconhecer
  a empresa/vaga rapidamente sem abrir o link.

## Template do texto (`text`, com `parse_mode: "HTML"`)

```
🆕 <b>{titulo}</b>
🏢 {empresa}
📍 {localizacao} ({modalidade_label})
🛠️ {stack_label}

<a href="{url}">Ver vaga</a>
```

### Regras de preenchimento

| Placeholder | Origem | Transformação |
|---|---|---|
| `{titulo}` | `vaga["titulo"]` | Escapar `<`, `>`, `&` (HTML entities) antes de inserir |
| `{empresa}` | `vaga["empresa"]` | Escapar `<`, `>`, `&` |
| `{localizacao}` | `vaga["localizacao"]` | Escapar `<`, `>`, `&` |
| `{modalidade_label}` | `vaga["modalidade"]` | `"remoto"` → `"Remoto"`, `"presencial"` → `"Presencial"`, `"hibrido"` → `"Híbrido"` |
| `{stack_label}` | `vaga["stack_detectada"]` | Join com `" · "`, capitalizado (ex.: `React · TypeScript`) |
| `{url}` | `vaga["url"]` | Sem alteração (URL crua, não a normalizada usada no hash) |

### Exemplo renderizado

```
🆕 Desenvolvedor(a) Full Stack Pleno (React/Node)
🏢 Acme Tecnologia Ltda
📍 Brasília, Distrito Federal, Brasil (Presencial)
🛠️ React · Node.js · Fullstack

Ver vaga (link)
```

## Tratamento de erro

- Resposta HTTP diferente de `200` (ou `ok: false` no corpo JSON de resposta do Telegram) é
  tratada como falha de envio. Conforme `plan.md` §3, isso impede o `INSERT` da vaga na tabela
  `vagas` — a vaga será reprocessada na próxima execução.
- Rate limit do Telegram (`HTTP 429`, campo `retry_after` no corpo) é um erro conhecido possível
  quando muitas vagas novas chegam na mesma execução; o tratamento (retry com backoff vs. apenas
  logar e deixar para a próxima execução do cron) é decisão de implementação da Fase 1, não desta
  spec — mas deve respeitar o Artigo IV (falha isolada não derruba o restante do pipeline).
