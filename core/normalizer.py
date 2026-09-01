from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

_logger = logging.getLogger(__name__)

# Única fonte da verdade para inferência de modalidade (scrapers/linkedin.py não implementa
# mais essa heurística — ver comentário em `_derivar_modalidade`). Prioridade 1: sinal
# explícito no próprio texto da vaga.
_MODALIDADE_PALAVRAS_CHAVE = (
    ("remoto", "remoto"),
    ("remote", "remoto"),
    ("home office", "remoto"),
    ("híbrido", "hibrido"),
    ("hibrido", "hibrido"),
    ("hybrid", "hibrido"),
    ("presencial", "presencial"),
    ("on-site", "presencial"),
    ("onsite", "presencial"),
)

# Prioridade 2 (fallback): o parâmetro `location` que scrapers/linkedin.py usou na própria
# busca ao LinkedIn (carregado no campo interno `_localidade_busca`). É um sinal mais confiável
# que qualquer heurística textual — é literalmente o filtro que fizemos o LinkedIn aplicar —,
# mas só é usado quando não há nenhuma palavra-chave explícita no texto da vaga.
_LOCALIDADE_BUSCA_PARA_MODALIDADE = {
    "remoto": "remoto",
    "brasilia": "presencial",
    "goiania": "presencial",
}

# Stack alinhada ao perfil real do usuário (linkedin.com/in/linsm7) — ver comentário em
# scrapers/linkedin.py::_TERMOS_BUSCA. Padrão de "react" vem antes do de "nextjs" na lista, mas a
# ordem entre eles não importa: `_detectar_stack` testa todos os padrões e não para no primeiro
# match, então uma vaga "Next.js + React" detecta ambos.
_STACK_PATTERNS = (
    (re.compile(r"\breact(\.js)?\b", re.IGNORECASE), "react"),
    (re.compile(r"\bnext(\.js)?\b", re.IGNORECASE), "nextjs"),
    (re.compile(r"\btypescript\b", re.IGNORECASE), "typescript"),
    (re.compile(r"\bnode(\.js)?\b", re.IGNORECASE), "node"),
    (re.compile(r"\bangular(js)?\b", re.IGNORECASE), "angular"),
    (re.compile(r"\bfull[\s-]?stack\b", re.IGNORECASE), "fullstack"),
)


def _normalizar_url(url: str) -> str:
    partes = urlsplit(url)
    sem_query_fragment = partes._replace(query="", fragment="")
    return urlunsplit(sem_query_fragment).rstrip("/")


def calcular_hash_unico(fonte: str, url: str) -> str:
    url_normalizada = _normalizar_url(url)
    return hashlib.sha256(f"{fonte}|{url_normalizada}".encode("utf-8")).hexdigest()


def _normalizar_texto(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower()


def _derivar_modalidade(vaga: dict) -> str | None:
    texto = " ".join(
        filter(None, [vaga.get("localizacao"), vaga.get("titulo"), vaga.get("descricao")])
    ).lower()
    for palavra, modalidade in _MODALIDADE_PALAVRAS_CHAVE:
        if palavra in texto:
            return modalidade

    # Sem sinal explícito no texto: cai para o contexto da busca, quando disponível. Evita os
    # dois erros já vistos: (1) assumir "presencial" às cegas descartava vagas remotas
    # legítimas cuja localização é vaga (ex.: "Brasil", sem anotação "(Remoto)"); (2) manter
    # sempre `None` reintroduzia o gap original de perder vagas presenciais/híbridas legítimas
    # em Brasília/Goiânia que o LinkedIn não anota explicitamente.
    localidade_busca = vaga.get("_localidade_busca")
    if localidade_busca:
        modalidade = _LOCALIDADE_BUSCA_PARA_MODALIDADE.get(_normalizar_texto(localidade_busca))
        if modalidade:
            return modalidade

    _logger.info(
        "Modalidade não classificável para '%s' (%s): sem palavra-chave explícita e sem "
        "contexto de busca reconhecido; mantendo modalidade=None (vaga será descartada pelo "
        "filtro de elegibilidade).",
        vaga.get("titulo"),
        vaga.get("url"),
    )
    return None


def _detectar_stack(vaga: dict) -> list[str]:
    if vaga.get("stack_detectada"):
        return vaga["stack_detectada"]
    texto = " ".join(filter(None, [vaga.get("titulo"), vaga.get("descricao")]))
    detectadas: list[str] = []
    for padrao, stack in _STACK_PATTERNS:
        if padrao.search(texto) and stack not in detectadas:
            detectadas.append(stack)
    return detectadas


def normalizar_vaga(vaga: dict) -> dict:
    vaga_normalizada = dict(vaga)

    if not vaga_normalizada.get("modalidade"):
        vaga_normalizada["modalidade"] = _derivar_modalidade(vaga_normalizada)

    vaga_normalizada["stack_detectada"] = _detectar_stack(vaga_normalizada)

    vaga_normalizada["hash_unico"] = calcular_hash_unico(
        vaga_normalizada["fonte"], vaga_normalizada["url"]
    )

    # Metadado interno do scraper, não faz parte do contrato público (vaga.schema.json) — some
    # depois de usado para não vazar para filters.py/telegram.py/database.py.
    vaga_normalizada.pop("_localidade_busca", None)

    return vaga_normalizada
