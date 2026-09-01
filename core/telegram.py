from __future__ import annotations

import html
import logging
import os

import requests

TELEGRAM_BOT_TOKEN_ENV_VAR = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_ENV_VAR = "TELEGRAM_CHAT_ID"

_API_BASE_URL = "https://api.telegram.org"
_TIMEOUT_SEGUNDOS = 10

_MODALIDADE_LABELS = {
    "remoto": "Remoto",
    "presencial": "Presencial",
    "hibrido": "Híbrido",
}
# Stack alinhada ao perfil real do usuário (linkedin.com/in/linsm7) — ver
# scrapers/linkedin.py::_TERMOS_BUSCA. Rótulo de "python" removido: o código "python" não é mais
# produzido por core/normalizer.py (stack não faz mais parte do perfil buscado), e `montar_mensagem`
# já cai de volta no código cru via `.get(stack, stack)` para qualquer valor sem rótulo mapeado,
# então mantê-lo aqui seria morto e potencialmente enganoso.
_STACK_LABELS = {
    "react": "React",
    "nextjs": "Next.js",
    "typescript": "TypeScript",
    "node": "Node.js",
    "angular": "Angular",
    "fullstack": "Fullstack",
}

_TEMPLATE = (
    "🆕 <b>{titulo}</b>\n"
    "🏢 {empresa}\n"
    "📍 {localizacao} ({modalidade_label})\n"
    "🛠️ {stack_label}\n"
    "\n"
    '<a href="{url}">Ver vaga</a>'
)

_logger = logging.getLogger(__name__)


def _escapar_html(texto: str) -> str:
    return html.escape(texto, quote=False)


def montar_mensagem(vaga: dict) -> str:
    modalidade_label = _MODALIDADE_LABELS[vaga["modalidade"]]
    stack_label = " · ".join(
        _STACK_LABELS.get(stack, stack) for stack in vaga["stack_detectada"]
    )
    return _TEMPLATE.format(
        titulo=_escapar_html(vaga["titulo"]),
        empresa=_escapar_html(vaga["empresa"]),
        localizacao=_escapar_html(vaga["localizacao"]),
        modalidade_label=modalidade_label,
        stack_label=stack_label,
        url=vaga["url"],
    )


def enviar_alerta(vaga: dict) -> bool:
    bot_token = os.environ.get(TELEGRAM_BOT_TOKEN_ENV_VAR)
    chat_id = os.environ.get(TELEGRAM_CHAT_ID_ENV_VAR)
    if not bot_token or not chat_id:
        raise RuntimeError(
            f"Variáveis de ambiente {TELEGRAM_BOT_TOKEN_ENV_VAR} e {TELEGRAM_CHAT_ID_ENV_VAR} "
            "precisam estar definidas (ver "
            "specs/001-bot-alertas-vagas/contracts/environment-variables.md)."
        )

    payload = {
        "chat_id": chat_id,
        "text": montar_mensagem(vaga),
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    url = f"{_API_BASE_URL}/bot{bot_token}/sendMessage"

    try:
        resposta = requests.post(url, json=payload, timeout=_TIMEOUT_SEGUNDOS)
    except requests.RequestException:
        _logger.exception("Falha de rede ao enviar alerta ao Telegram para %s", vaga.get("url"))
        return False

    if resposta.status_code != 200:
        _logger.error(
            "Telegram respondeu HTTP %s ao notificar %s: %s",
            resposta.status_code,
            vaga.get("url"),
            resposta.text,
        )
        return False

    corpo = resposta.json()
    if not corpo.get("ok", False):
        _logger.error("Telegram respondeu ok=false ao notificar %s: %s", vaga.get("url"), corpo)
        return False

    return True
