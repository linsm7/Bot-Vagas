from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timezone

import requests
from bs4 import BeautifulSoup

FONTE = "gupy"

# `employability-portal.gupy.io/api/v1/jobs` é a API JSON pública (sem autenticação) que
# alimenta a busca de vagas em portal.gupy.io/job-search — a busca agregada em si é renderizada
# no cliente (Next.js), então não dá para raspar o HTML de portal.gupy.io diretamente como no
# LinkedIn; esta é a chamada real feita pelo navegador (descoberta via
# performance.getEntriesByType('resource') na página de busca). Não documentada publicamente,
# então sujeita a mudar sem aviso — mesmo risco aceito de qualquer scraping de terceiro
# (Artigo IV da constituição): uma falha aqui derruba só esta fonte.
_API_BASE_URL = "https://employability-portal.gupy.io/api/v1/jobs"
_TIMEOUT_SEGUNDOS = 10
_LIMITE_POR_BUSCA = 50
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Mesmos termos de busca do LinkedIn (spec.md §4) — ver scrapers/linkedin.py::_TERMOS_BUSCA.
_TERMOS_BUSCA = ("React", "Next.js", "TypeScript", "Node.js", "Angular", "Full Stack")
# A API aceita `city` como filtro de localização (validado empiricamente: `city=Brasília`
# restringe corretamente). Usado só para as buscas presenciais/híbridas — a busca remota não
# filtra por cidade (ver `buscar_vagas`).
_CIDADES_PRESENCIAL = ("Brasília", "Goiânia")

# Diferente do LinkedIn, a Gupy já devolve `workplaceType` explícito por vaga — não precisamos
# inferir modalidade por palavra-chave (core/normalizer.py::_derivar_modalidade só entra em ação
# quando `modalidade` vem `None`, o que não acontece aqui para um `workplaceType` reconhecido).
_WORKPLACE_TYPE_PARA_MODALIDADE = {
    "remote": "remoto",
    "hybrid": "hibrido",
    "on-site": "presencial",
}

_logger = logging.getLogger(__name__)


def _user_agent() -> str:
    return os.environ.get("HTTP_USER_AGENT") or _DEFAULT_USER_AGENT


def _parsear_data_publicacao(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor[:10])
    except ValueError:
        return None


def _montar_localizacao(job: dict) -> str:
    partes = [parte for parte in (job.get("city"), job.get("state"), job.get("country")) if parte]
    if partes:
        return ", ".join(partes)
    return "Remoto" if job.get("workplaceType") == "remote" else "Brasil"


def _extrair_vaga(job: dict) -> dict | None:
    try:
        titulo = (job.get("name") or "").strip()
        empresa = (job.get("careerPageName") or "").strip()
        url = (job.get("jobUrl") or "").strip()
        if not titulo or not empresa or not url:
            return None

        # A API já devolve a descrição completa (HTML) na própria resposta de busca — ao
        # contrário do LinkedIn/Indeed/Empregare, não precisamos de uma segunda requisição para
        # ter texto suficiente para os critérios de nível/inglês (spec.md §4, itens 6-7). Ver
        # `buscar_descricao_completa` abaixo, que só é chamada pelo pipeline quando `descricao`
        # ainda é `None` — o que não é o caso das vagas da Gupy.
        descricao_html = job.get("description") or ""
        descricao = BeautifulSoup(descricao_html, "html.parser").get_text(separator="\n", strip=True)

        return {
            "titulo": titulo,
            "empresa": empresa,
            "localizacao": _montar_localizacao(job),
            "modalidade": _WORKPLACE_TYPE_PARA_MODALIDADE.get(job.get("workplaceType")),
            "url": url,
            "fonte": FONTE,
            "descricao": descricao,
            "stack_detectada": [],
            "data_publicacao": _parsear_data_publicacao(job.get("publishedDate")),
            "data_coleta": datetime.now(timezone.utc),
            "hash_unico": None,
        }
    except Exception:
        _logger.exception("Falha ao extrair uma vaga da resposta da API da Gupy; ignorando")
        return None


def _buscar_uma_combinacao(termo: str, cidade: str | None) -> list[dict]:
    params: dict[str, str | int] = {"jobName": termo, "limit": _LIMITE_POR_BUSCA}
    if cidade:
        params["city"] = cidade
    headers = {"User-Agent": _user_agent(), "Accept": "application/json"}

    try:
        resposta = requests.get(_API_BASE_URL, params=params, headers=headers, timeout=_TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
    except requests.RequestException:
        _logger.exception("Falha de rede ao buscar '%s' (cidade=%s) na API da Gupy", termo, cidade)
        return []

    try:
        corpo = resposta.json()
        jobs = corpo.get("data") or []
    except ValueError:
        _logger.exception("Falha ao parsear a resposta JSON da API da Gupy para '%s'", termo)
        return []

    vagas = [_extrair_vaga(job) for job in jobs]
    return [vaga for vaga in vagas if vaga is not None]


def buscar_vagas() -> list[dict]:
    vagas_por_url: dict[str, dict] = {}
    for termo in _TERMOS_BUSCA:
        # Remoto: sem filtro de cidade. A API já devolve `country`/`workplaceType` por vaga, mas
        # o filtro real e obrigatório de "remoto só do Brasil" continua sendo
        # core/filters.py::_modalidade_localizacao_elegivel (mesma decisão já tomada para o
        # LinkedIn) — aplicado igual para as quatro fontes.
        for vaga in _buscar_uma_combinacao(termo, cidade=None):
            vagas_por_url.setdefault(vaga["url"], vaga)
        for cidade in _CIDADES_PRESENCIAL:
            for vaga in _buscar_uma_combinacao(termo, cidade):
                vagas_por_url.setdefault(vaga["url"], vaga)
    return list(vagas_por_url.values())


def buscar_descricao_completa(url: str) -> str | None:
    """Busca a página individual da vaga na Gupy e extrai a descrição completa.

    Na prática, quase nunca é chamada para vagas da Gupy: `buscar_vagas` já preenche
    `descricao` a partir da própria resposta de busca (ver `_extrair_vaga`), e
    `main.py::executar_pipeline` só chama esta função quando `vaga["descricao"]` ainda é `None`.
    Implementada mesmo assim para cumprir o mesmo contrato dos outros scrapers
    (`scrapers/base.py`) e cobrir o caso raro de a busca ter devolvido descrição vazia: a página
    individual de uma vaga na Gupy (`<empresa>.gupy.io/job/...`) é renderizada no servidor
    (Next.js `getServerSideProps`), com os dados completos da vaga embutidos no
    `<script id="__NEXT_DATA__">` — diferente da busca agregada em portal.gupy.io, que só
    renderiza no cliente.
    """
    headers = {"User-Agent": _user_agent(), "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}

    try:
        resposta = requests.get(url, headers=headers, timeout=_TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
    except requests.RequestException:
        _logger.exception("Falha de rede ao buscar a página individual da vaga %s na Gupy", url)
        return None

    try:
        soup = BeautifulSoup(resposta.text, "html.parser")
        script = soup.select_one("script#__NEXT_DATA__")
        if script is None or not script.string:
            return ""
        dados = json.loads(script.string)
        job = dados.get("props", {}).get("pageProps", {}).get("job", {}) or {}
        descricao_html = job.get("description") or ""
        return BeautifulSoup(descricao_html, "html.parser").get_text(separator="\n", strip=True)
    except Exception:
        _logger.exception("Falha ao parsear a página individual da vaga %s na Gupy", url)
        return None
