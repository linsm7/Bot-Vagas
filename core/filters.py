from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

# Stack alinhada ao perfil real do usuário (linkedin.com/in/linsm7) — ver comentário em
# scrapers/linkedin.py::_TERMOS_BUSCA e core/normalizer.py::_STACK_PATTERNS.
_STACKS_ACEITAS = frozenset({"react", "nextjs", "typescript", "node", "angular", "fullstack"})

# --- Recência (spec.md §4) ---------------------------------------------------------------
_JANELA_RECENCIA_DIAS = 7

# --- Nível (spec.md §4) -------------------------------------------------------------------
# Só júnior/pleno são elegíveis. Termos de sênior/especialista são checados primeiro porque
# títulos como "Desenvolvedor Pleno/Sênior" (faixa dupla) devem contar como sênior — mais
# restritivo prevalece em caso de ambiguidade textual.
# Padrões são testados contra texto já normalizado por `_normalizar_texto` (sem acento, minúsculo)
# — por isso não precisam de variantes acentuadas (ex.: "junior" cobre o "júnior" já normalizado).
_NIVEL_SENIOR_PATTERNS = (
    re.compile(r"\bsenior\b"),
    re.compile(r"\bsr\.?\b"),
    re.compile(r"\bespecialista\b"),
    re.compile(r"\bstaff\b"),
    re.compile(r"\blead(er)?\b"),
    re.compile(r"\bprincipal\b"),
)
_NIVEL_JUNIOR_PLENO_PATTERNS = (
    re.compile(r"\bjunior\b"),
    re.compile(r"\bjr\.?\b"),
    re.compile(r"\bpleno\b"),
    re.compile(r"\bmid[\s-]?level\b"),
    re.compile(r"\bentry[\s-]?level\b"),
)

# --- Inglês não exigido (spec.md §4) -------------------------------------------------------
# Não exaustiva por design (Artigo I da constituição — simplicidade), mesma filosofia já
# registrada para _LOCALIZACOES_ELEGIVEIS logo abaixo. Cobre as formas mais comuns em vagas
# pt-BR e en-US/en-GB; pode ser ampliada com bom senso conforme falsos negativos aparecerem.
_EXIGENCIA_INGLES_PATTERNS = (
    re.compile(r"ingl[eê]s\s+(avan[cç]ado|fluente|intermedi[aá]rio\s+avan[cç]ado)", re.IGNORECASE),
    re.compile(r"(necess[aá]rio|obrigat[oó]rio|exig[ie]|requer)[^.\n]{0,20}ingl[eê]s", re.IGNORECASE),
    re.compile(r"ingl[eê]s[^.\n]{0,20}(obrigat[oó]rio|necess[aá]rio|indispens[aá]vel)", re.IGNORECASE),
    re.compile(r"(advanced|fluent|proficient)[^.\n]{0,10}(in\s+)?english", re.IGNORECASE),
    re.compile(r"english[^.\n]{0,20}(required|mandatory|fluency)", re.IGNORECASE),
    re.compile(r"\bfluent\s+english\b", re.IGNORECASE),
)

# Não exaustiva por design (Artigo I da constituição — simplicidade): cobre o Distrito Federal
# (Brasília e as principais cidades da região metropolitana) e Goiânia/região metropolitana,
# conforme os exemplos citados em data-model.md §2.
_LOCALIZACOES_ELEGIVEIS = (
    "brasilia",
    "distrito federal",
    "aguas claras",
    "taguatinga",
    "ceilandia",
    "samambaia",
    "planaltina",
    "sobradinho",
    "goiania",
    "aparecida de goiania",
)
_DF_REGEX = re.compile(r"\bdf\b")


def _normalizar_texto(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower()


def _localizacao_elegivel(localizacao: str) -> bool:
    normalizado = _normalizar_texto(localizacao)
    if any(chave in normalizado for chave in _LOCALIZACOES_ELEGIVEIS):
        return True
    return bool(_DF_REGEX.search(normalizado))


def _modalidade_localizacao_elegivel(vaga: dict) -> bool:
    modalidade = vaga.get("modalidade")
    if modalidade == "remoto":
        return True
    if modalidade in ("presencial", "hibrido"):
        return _localizacao_elegivel(vaga.get("localizacao") or "")
    return False


def vaga_recente(vaga: dict, agora: datetime | None = None) -> bool:
    data_publicacao: date | None = vaga.get("data_publicacao")
    if data_publicacao is None:
        # DECISÃO (spec.md §4): o card de busca do LinkedIn frequentemente não expõe
        # `<time datetime="...">` de forma parseável (ver scrapers/linkedin.py::
        # _parsear_data_publicacao), então `data_publicacao=None` é comum mesmo para vagas
        # recém-publicadas — não é sinal de que a vaga seja antiga. Descartar por padrão
        # reintroduziria o mesmo tipo de perda de vagas legítimas já evitado para modalidade
        # (ver core/normalizer.py::_derivar_modalidade). Por isso a decisão é ACEITAR quando a
        # data é desconhecida, e só descartar quando *sabemos* que a vaga é antiga.
        return True
    limite = (agora or datetime.now(timezone.utc)).date() - timedelta(days=_JANELA_RECENCIA_DIAS)
    return data_publicacao >= limite


def _nivel_detectado(texto: str) -> str | None:
    if any(padrao.search(texto) for padrao in _NIVEL_SENIOR_PATTERNS):
        return "senior"
    if any(padrao.search(texto) for padrao in _NIVEL_JUNIOR_PLENO_PATTERNS):
        return "junior_pleno"
    return None


def nivel_elegivel(vaga: dict) -> bool:
    descricao = vaga.get("descricao")
    if descricao is None:
        # Descrição completa ainda não foi buscada (ver main.py::executar_pipeline — só é
        # buscada depois dos filtros baratos). Retornar True aqui não declara a vaga elegível
        # de fato; apenas evita bloquear o portão barato antes de sabermos o nível. A checagem
        # real acontece na segunda chamada a `vaga_elegivel`, já com a descrição preenchida.
        return True

    texto = _normalizar_texto(" ".join(filter(None, [vaga.get("titulo"), descricao])))
    nivel = _nivel_detectado(texto)
    if nivel == "senior":
        return False
    if nivel == "junior_pleno":
        return True

    # DECISÃO (spec.md §4): nenhum sinal textual de nível encontrado (nem júnior/pleno, nem
    # sênior/especialista). Muitas vagas júnior/pleno legítimas simplesmente não anotam o nível
    # explicitamente no texto. Ser restritivo aqui (descartar por falta de prova) jogaria fora
    # vagas relevantes de verdade — o mesmo tipo de custo (perder vaga boa) que a spec já
    # considera pior do que ocasionalmente notificar uma vaga cujo nível real seja incerto.
    # Por isso a decisão é ACEITAR por padrão quando não há sinal textual de nível.
    return True


def ingles_exigido(vaga: dict) -> bool:
    descricao = vaga.get("descricao")
    if descricao is None:
        # Mesma lógica de `nivel_elegivel`: sem descrição completa ainda, não bloqueia o portão
        # barato. `False` aqui significa "não sabemos que inglês é exigido", não "sabemos que
        # não é".
        return False

    texto = " ".join(filter(None, [vaga.get("titulo"), descricao]))
    return any(padrao.search(texto) for padrao in _EXIGENCIA_INGLES_PATTERNS)


def vaga_elegivel(vaga: dict) -> bool:
    stacks_validas = _STACKS_ACEITAS.intersection(vaga.get("stack_detectada") or [])
    if not stacks_validas:
        return False

    if not _modalidade_localizacao_elegivel(vaga):
        return False

    if not vaga_recente(vaga):
        return False

    if not nivel_elegivel(vaga):
        return False

    if ingles_exigido(vaga):
        return False

    return True
