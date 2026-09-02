from __future__ import annotations

import logging
import os
import unicodedata
from datetime import date, datetime, timezone

import requests
from bs4 import BeautifulSoup

FONTE = "empregare"

# API JSON pública (sem autenticação) que alimenta a busca em empregare.com/pt-br/vagas — a
# página em si só renderiza um esqueleto de loading no HTML inicial (busca é client-side); esta é
# a chamada real feita pelo navegador (descoberta via performance.getEntriesByType('resource') na
# página de busca). Não documentada publicamente — mesmo risco aceito de qualquer scraping de
# terceiro (Artigo IV da constituição).
_API_BASE_URL = "https://www.empregare.com/api/pt-br/vagas/buscar-novo"
_BASE_JOB_URL = "https://www.empregare.com/pt-br/"
_TIMEOUT_SEGUNDOS = 10
_ITENS_POR_PAGINA = 50
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Mesmos termos de busca do LinkedIn (spec.md §4) — ver scrapers/linkedin.py::_TERMOS_BUSCA.
_TERMOS_BUSCA = ("React", "Next.js", "TypeScript", "Node.js", "Angular", "Full Stack")
# Formato exigido pelo parâmetro `localidade` da API (visto no facet `cidade` da própria
# resposta): "<Cidade>, <UF>, BR". Usado só para as buscas presenciais/híbridas — a busca sem
# `localidade` já devolve todas as modalidades (inclusive remoto), mas mantemos os dois passes
# extras por cidade (mesmo padrão do LinkedIn/Gupy) para não depender de paginação: um termo
# popular sem filtro de cidade pode ter mais resultados nacionais do que `_ITENS_POR_PAGINA`,
# e uma vaga presencial legítima em Brasília/Goiânia poderia ficar de fora da primeira página.
_CIDADES_PRESENCIAL = ("Brasília, DF, BR", "Goiânia, GO, BR")

_logger = logging.getLogger(__name__)


def _user_agent() -> str:
    return os.environ.get("HTTP_USER_AGENT") or _DEFAULT_USER_AGENT


def _normalizar_texto(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower()


# Diferente do LinkedIn/Indeed, a Empregare já devolve um rótulo de modalidade por vaga
# (`trabalhoRemotoTexto`, ex.: "Presencial", "Híbrido", "Totalmente Remoto") — não precisamos
# inferir por palavra-chave no texto da vaga (core/normalizer.py só entra em ação se isto
# devolver `None`). Mapeamento por substring (não por valor exato do enum bruto
# `trabalhoRemoto`, ex. "RemotoFlexivel") porque o rótulo textual é mais estável a mudanças
# futuras do enum interno da API.
def _modalidade_de_rotulo(rotulo: str | None) -> str | None:
    normalizado = _normalizar_texto(rotulo or "")
    if "hibrido" in normalizado:
        return "hibrido"
    if "remoto" in normalizado:
        return "remoto"
    if "presencial" in normalizado:
        return "presencial"
    return None


def _parsear_data_publicacao(timestamp) -> date | None:
    if not timestamp:
        return None
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).date()
    except (OverflowError, OSError, ValueError, TypeError):
        return None


def _montar_localizacao(dado: dict) -> str:
    cidades = [cidade for cidade in (dado.get("cidades") or []) if cidade]
    if cidades:
        return "; ".join(cidades)
    return "Brasil"


def _extrair_vaga(dado: dict) -> dict | None:
    try:
        titulo = (dado.get("titulo") or "").strip()
        empresa = (dado.get("empresa") or "").strip()
        slug = (dado.get("url") or "").strip()
        if not titulo or not empresa or not slug:
            return None

        return {
            "titulo": titulo,
            "empresa": empresa,
            "localizacao": _montar_localizacao(dado),
            "modalidade": _modalidade_de_rotulo(dado.get("trabalhoRemotoTexto")),
            "url": f"{_BASE_JOB_URL}{slug}",
            "fonte": FONTE,
            # `chamada` (campo da API) é só um teaser truncado, não a descrição completa — segue
            # `None`, mesma semântica do LinkedIn/Indeed: `buscar_descricao_completa` busca o
            # texto completo depois, só para vagas que já passaram nos filtros baratos.
            "descricao": None,
            "stack_detectada": [],
            "data_publicacao": _parsear_data_publicacao(dado.get("timestamp")),
            "data_coleta": datetime.now(timezone.utc),
            "hash_unico": None,
        }
    except Exception:
        _logger.exception("Falha ao extrair uma vaga da resposta da API da Empregare; ignorando")
        return None


def _buscar_uma_combinacao(termo: str, localidade: str | None) -> list[dict]:
    params = {
        "pagina": 1,
        "itensPagina": _ITENS_POR_PAGINA,
        "query": termo,
        "localidade": localidade or "",
        "q": "",
        "empresa": "",
        "hotSiteUrl": "",
    }
    headers = {"User-Agent": _user_agent(), "Accept": "application/json"}

    try:
        resposta = requests.get(_API_BASE_URL, params=params, headers=headers, timeout=_TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
    except requests.RequestException:
        _logger.exception(
            "Falha de rede ao buscar '%s' (localidade=%s) na API da Empregare", termo, localidade
        )
        return []

    try:
        corpo = resposta.json()
        if not corpo.get("sucesso"):
            _logger.warning(
                "API da Empregare respondeu sucesso=false para '%s' (localidade=%s)", termo, localidade
            )
            return []
        dados = corpo.get("model", {}).get("dados") or []
    except ValueError:
        _logger.exception("Falha ao parsear a resposta JSON da API da Empregare para '%s'", termo)
        return []

    vagas = [_extrair_vaga(dado) for dado in dados]
    return [vaga for vaga in vagas if vaga is not None]


def buscar_vagas() -> list[dict]:
    vagas_por_url: dict[str, dict] = {}
    for termo in _TERMOS_BUSCA:
        # Sem filtro de localidade: já cobre remoto (e presencial/híbrido de qualquer cidade,
        # descartado depois por core/filters.py se não for Brasília/Goiânia).
        for vaga in _buscar_uma_combinacao(termo, localidade=None):
            vagas_por_url.setdefault(vaga["url"], vaga)
        for cidade in _CIDADES_PRESENCIAL:
            for vaga in _buscar_uma_combinacao(termo, cidade):
                vagas_por_url.setdefault(vaga["url"], vaga)
    return list(vagas_por_url.values())


# Seletor conhecido do markup da página individual de uma vaga da Empregare (renderizada no
# servidor, ao contrário da busca) — validado manualmente contra empregare.com/pt-br/vaga-*.
_SELETOR_DESCRICAO_COMPLETA = "#vaga-descricao"


def buscar_descricao_completa(url: str) -> str | None:
    """Busca a página individual de uma vaga na Empregare e extrai o texto da descrição completa.

    Mesmo contrato/motivo de scrapers/linkedin.py::buscar_descricao_completa.
    """
    headers = {"User-Agent": _user_agent(), "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}

    try:
        resposta = requests.get(url, headers=headers, timeout=_TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
    except requests.RequestException:
        _logger.exception("Falha de rede ao buscar a descrição completa da vaga %s (Empregare)", url)
        return None

    try:
        soup = BeautifulSoup(resposta.text, "html.parser")
        elemento = soup.select_one(_SELETOR_DESCRICAO_COMPLETA)
        if elemento is None:
            return ""
        return elemento.get_text(separator="\n", strip=True)
    except Exception:
        _logger.exception("Falha ao parsear o HTML da página da vaga %s (Empregare)", url)
        return None
