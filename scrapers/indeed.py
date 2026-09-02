from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

FONTE = "indeed"

_BASE_SEARCH_URL = "https://br.indeed.com/jobs"
_BASE_JOB_URL = "https://br.indeed.com/viewjob"
_TIMEOUT_SEGUNDOS = 10
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Mesmos termos/localidades de busca do LinkedIn (spec.md §4) — ver
# scrapers/linkedin.py::_TERMOS_BUSCA/_LOCALIDADES_BUSCA. `l=Remoto`/`l=Brasília`/`l=Goiânia`
# validados manualmente contra br.indeed.com/jobs — são valores aceitos pelo parâmetro `l`
# (localização) da busca pública.
_TERMOS_BUSCA = ("React", "Next.js", "TypeScript", "Node.js", "Angular", "Full Stack")
_LOCALIDADES_BUSCA = ("Remoto", "Brasília", "Goiânia")

_logger = logging.getLogger(__name__)


def _user_agent() -> str:
    return os.environ.get("HTTP_USER_AGENT") or _DEFAULT_USER_AGENT


def _montar_url_busca(termo: str, localidade: str) -> str:
    params = {"q": termo, "l": localidade}
    return f"{_BASE_SEARCH_URL}?{urlencode(params)}"


def _extrair_vaga(card, localidade_busca: str) -> dict | None:
    try:
        link_el = card.select_one("a[data-jk]")
        if link_el is None:
            return None
        job_key = (link_el.get("data-jk") or "").strip()
        if not job_key:
            return None

        titulo_el = link_el.select_one("span[title]") or card.select_one("[id^='jobTitle']")
        empresa_el = card.select_one('span[data-testid="company-name"]')
        localizacao_el = card.select_one('div[data-testid="text-location"]')

        if titulo_el is None or empresa_el is None:
            return None

        titulo = titulo_el.get_text(strip=True)
        empresa = empresa_el.get_text(strip=True)
        if not titulo or not empresa:
            return None

        localizacao = localizacao_el.get_text(strip=True) if localizacao_el else localidade_busca

        return {
            "titulo": titulo,
            "empresa": empresa,
            "localizacao": localizacao,
            # `modalidade` não é inferida aqui — core/normalizer.py é a única fonte da verdade
            # para essa regra (mesma decisão do LinkedIn, ver scrapers/linkedin.py::_extrair_vaga).
            "modalidade": None,
            "url": f"{_BASE_JOB_URL}?jk={job_key}",
            "fonte": FONTE,
            "descricao": None,
            "stack_detectada": [],
            # O card de busca do Indeed não expõe uma data de publicação parseável de forma
            # confiável (só texto relativo tipo "há 3 dias", inconsistente entre cards) — mesma
            # decisão já tomada para o LinkedIn (spec.md §4 item 4): ausência de
            # `data_publicacao` não descarta a vaga por si só.
            "data_publicacao": None,
            "data_coleta": datetime.now(timezone.utc),
            "hash_unico": None,
            # Campo interno, mesmo propósito documentado em scrapers/linkedin.py::_extrair_vaga:
            # fallback de modalidade em core/normalizer.py quando não há palavra-chave explícita
            # no texto da vaga.
            "_localidade_busca": localidade_busca,
        }
    except Exception:
        _logger.exception("Falha ao extrair um card de vaga do Indeed; ignorando este card")
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
        # LIMITAÇÃO CONHECIDA (documentada no relatório da tarefa): o Indeed tem proteção
        # anti-bot forte (Cloudflare) e bloqueia a maioria das requisições feitas via `requests`
        # puro (sem execução de JS) — validado manualmente: uma requisição simples a esta URL
        # recebe 403 imediatamente, mesmo com um User-Agent de navegador real. Um IP de
        # datacenter (ex.: runner do GitHub Actions) tem chance ainda maior de ser bloqueado.
        # Tratado como falha de rede normal (Artigo IV): loga e retorna lista vazia, sem derrubar
        # o pipeline nem as outras fontes.
        _logger.exception("Falha de rede (possível bloqueio anti-bot) ao buscar '%s' em '%s' no Indeed", termo, localidade)
        return []

    try:
        soup = BeautifulSoup(resposta.text, "html.parser")
        cards = soup.select("div.job_seen_beacon")
    except Exception:
        _logger.exception(
            "Falha ao parsear o HTML da busca '%s' em '%s' no Indeed", termo, localidade
        )
        return []

    vagas = [_extrair_vaga(card, localidade) for card in cards]
    return [vaga for vaga in vagas if vaga is not None]


def buscar_vagas() -> list[dict]:
    vagas_por_url: dict[str, dict] = {}
    for termo in _TERMOS_BUSCA:
        for localidade in _LOCALIDADES_BUSCA:
            for vaga in _buscar_uma_combinacao(termo, localidade):
                vagas_por_url.setdefault(vaga["url"], vaga)
    return list(vagas_por_url.values())


# Seletor conhecido do markup da página individual de uma vaga do Indeed (distinto do markup do
# card de busca) — validado manualmente contra br.indeed.com/viewjob.
_SELETOR_DESCRICAO_COMPLETA = "#jobDescriptionText"


def buscar_descricao_completa(url: str) -> str | None:
    """Busca a página individual de uma vaga no Indeed e extrai o texto da descrição completa.

    Mesmo contrato/motivo de scrapers/linkedin.py::buscar_descricao_completa. Sujeita à mesma
    limitação de bloqueio anti-bot documentada em `_buscar_uma_combinacao` acima — uma falha de
    rede aqui descarta a vaga *nesta* execução (será tentada de novo na próxima), sem derrubar o
    pipeline.
    """
    headers = {
        "User-Agent": _user_agent(),
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }

    try:
        resposta = requests.get(url, headers=headers, timeout=_TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
    except requests.RequestException:
        _logger.exception("Falha de rede ao buscar a descrição completa da vaga %s (Indeed)", url)
        return None

    try:
        soup = BeautifulSoup(resposta.text, "html.parser")
        elemento = soup.select_one(_SELETOR_DESCRICAO_COMPLETA)
        if elemento is None:
            return ""
        return elemento.get_text(separator="\n", strip=True)
    except Exception:
        _logger.exception("Falha ao parsear o HTML da página da vaga %s (Indeed)", url)
        return None
