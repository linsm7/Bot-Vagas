from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

FONTE = "linkedin"

_BASE_SEARCH_URL = "https://www.linkedin.com/jobs/search/"
_TIMEOUT_SEGUNDOS = 10
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Termos de busca e localidades conforme spec.md §4. Mantidos como constantes de código, não
# como variáveis de ambiente — mesma decisão já registrada para core/filters.py em
# contracts/environment-variables.md.
# Stack alinhada ao perfil real do usuário (linkedin.com/in/linsm7): Next.js, React.js,
# TypeScript, Node.js e Angular são as "Principais competências" do perfil; Python foi removido
# por não ter nenhuma evidência de uso no perfil. "Full Stack" é mantido por ser literalmente o
# título de cargo do usuário.
_TERMOS_BUSCA = ("React", "Next.js", "TypeScript", "Node.js", "Angular", "Full Stack")
_LOCALIDADES_BUSCA = ("Remoto", "Brasília", "Goiânia")

_logger = logging.getLogger(__name__)


def _user_agent() -> str:
    return os.environ.get("HTTP_USER_AGENT") or _DEFAULT_USER_AGENT


def _montar_url_busca(termo: str, localidade: str) -> str:
    params = {"keywords": termo, "location": localidade}
    return f"{_BASE_SEARCH_URL}?{urlencode(params)}"


def _parsear_data_publicacao(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return None


def _extrair_vaga(card, localidade_busca: str) -> dict | None:
    try:
        titulo_el = card.select_one("h3.base-search-card__title")
        empresa_el = card.select_one("h4.base-search-card__subtitle")
        localizacao_el = card.select_one("span.job-search-card__location")
        link_el = card.select_one("a.base-card__full-link") or card.select_one("a[href]")
        data_el = card.select_one("time")

        if titulo_el is None or empresa_el is None or link_el is None:
            return None

        titulo = titulo_el.get_text(strip=True)
        empresa = empresa_el.get_text(strip=True)
        url = (link_el.get("href") or "").strip()

        if not titulo or not empresa or not url:
            return None

        localizacao = localizacao_el.get_text(strip=True) if localizacao_el else localidade_busca

        return {
            "titulo": titulo,
            "empresa": empresa,
            "localizacao": localizacao,
            # `modalidade` não é inferida aqui — core/normalizer.py é a única fonte da verdade
            # para essa regra (evita a duplicação de heurística entre scraper e normalizador).
            "modalidade": None,
            "url": url,
            "fonte": FONTE,
            "descricao": None,
            "stack_detectada": [],
            "data_publicacao": _parsear_data_publicacao(data_el.get("datetime") if data_el else None),
            "data_coleta": datetime.now(timezone.utc),
            "hash_unico": None,
            # Campo interno, fora do contrato público de vaga.schema.json (que permite
            # additionalProperties) — registra qual parâmetro `location` foi usado na busca ao
            # LinkedIn que retornou este card. É um sinal mais confiável que qualquer inferência
            # textual (é literalmente o filtro que fizemos a LinkedIn aplicar), usado só por
            # core/normalizer.py como fallback quando não há palavra-chave explícita no texto da
            # vaga; removido do dict antes de seguir para o resto do pipeline.
            "_localidade_busca": localidade_busca,
        }
    except Exception:
        _logger.exception("Falha ao extrair um card de vaga do LinkedIn; ignorando este card")
        return None


def _buscar_uma_combinacao(termo: str, localidade: str) -> list[dict]:
    url = _montar_url_busca(termo, localidade)
    headers = {
        "User-Agent": _user_agent(),
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }

    try:
        resposta = requests.get(url, headers=headers, timeout=_TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
    except requests.RequestException:
        _logger.exception("Falha de rede ao buscar '%s' em '%s' no LinkedIn", termo, localidade)
        return []

    try:
        soup = BeautifulSoup(resposta.text, "html.parser")
        cards = soup.select("div.base-card")
    except Exception:
        _logger.exception(
            "Falha ao parsear o HTML da busca '%s' em '%s' no LinkedIn", termo, localidade
        )
        return []

    vagas = [_extrair_vaga(card, localidade) for card in cards]
    return [vaga for vaga in vagas if vaga is not None]


# Seletores conhecidos do markup da página pública de uma vaga individual do LinkedIn (distinto
# do markup do card de busca). Tentados em ordem; o primeiro que casar é usado.
_SELETORES_DESCRICAO_COMPLETA = (
    "div.show-more-less-html__markup",
    "div.description__text",
)


def buscar_descricao_completa(url: str) -> str | None:
    """Busca a página individual de uma vaga e extrai o texto da descrição completa.

    Usada pelo pipeline (main.py) apenas para vagas que já passaram nos filtros baratos
    (stack/localização/modalidade/recência) e ainda não foram notificadas — ver spec.md §4 e o
    comentário em main.py::executar_pipeline sobre a ordem das checagens.

    Retorno:
    - `str` (pode ser vazia) quando a página foi buscada e parseada com sucesso.
    - `None` quando não foi possível verificar (falha de rede ou de parsing) — sinal para o
      pipeline descartar a vaga *nesta* execução, sem gravar no banco; como o registro só
      acontece após notificação confirmada, a vaga será tentada de novo na próxima execução.
    """
    headers = {
        "User-Agent": _user_agent(),
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }

    try:
        resposta = requests.get(url, headers=headers, timeout=_TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
    except requests.RequestException:
        _logger.exception("Falha de rede ao buscar a descrição completa da vaga %s", url)
        return None

    try:
        soup = BeautifulSoup(resposta.text, "html.parser")
        for seletor in _SELETORES_DESCRICAO_COMPLETA:
            elemento = soup.select_one(seletor)
            if elemento is not None:
                return elemento.get_text(separator="\n", strip=True)
        # Página carregou e parseou normalmente, mas nenhum seletor conhecido bateu (markup
        # mudou, ou a vaga não tem seção de descrição). Não é uma falha de verificação — é uma
        # descrição vazia legítima, então segue como string vazia (não None) para os filtros que
        # dependem de descrição (core/filters.py) tratarem como "sem sinal de texto".
        return ""
    except Exception:
        _logger.exception("Falha ao parsear o HTML da página da vaga %s", url)
        return None


def buscar_vagas() -> list[dict]:
    vagas_por_url: dict[str, dict] = {}
    for termo in _TERMOS_BUSCA:
        for localidade in _LOCALIDADES_BUSCA:
            for vaga in _buscar_uma_combinacao(termo, localidade):
                # Mesma vaga pode aparecer em buscas por termos diferentes (ex.: "React" e
                # "Full Stack"); mantém a primeira ocorrência.
                vagas_por_url.setdefault(vaga["url"], vaga)
    return list(vagas_por_url.values())
