from __future__ import annotations

import os
import re

import psycopg2
import psycopg2.extensions

DATABASE_URL_ENV_VAR = "DATABASE_URL"

_CAMPOS_OBRIGATORIOS = (
    "titulo",
    "empresa",
    "localizacao",
    "modalidade",
    "url",
    "fonte",
    "stack_detectada",
    "data_coleta",
    "hash_unico",
)
_MODALIDADES_VALIDAS = {"remoto", "presencial", "hibrido"}
_HASH_UNICO_RE = re.compile(r"^[a-f0-9]{64}$")

_INSERT_SQL = """
    INSERT INTO vagas (
        titulo, empresa, localizacao, modalidade, url, fonte,
        descricao, stack_detectada, data_publicacao, data_coleta, hash_unico
    )
    VALUES (
        %(titulo)s, %(empresa)s, %(localizacao)s, %(modalidade)s, %(url)s, %(fonte)s,
        %(descricao)s, %(stack_detectada)s, %(data_publicacao)s, %(data_coleta)s, %(hash_unico)s
    )
    ON CONFLICT (hash_unico) DO NOTHING
    RETURNING id
"""


def get_connection() -> psycopg2.extensions.connection:
    database_url = os.environ.get(DATABASE_URL_ENV_VAR)
    if not database_url:
        raise RuntimeError(
            f"Variável de ambiente {DATABASE_URL_ENV_VAR} não definida. Configure-a com a "
            "connection string do Neon Postgres (ver "
            "specs/001-bot-alertas-vagas/contracts/environment-variables.md)."
        )
    return psycopg2.connect(database_url)


def vaga_ja_existe(conn: psycopg2.extensions.connection, hash_unico: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM vagas WHERE hash_unico = %s LIMIT 1", (hash_unico,))
        return cur.fetchone() is not None


def inserir_vaga(conn: psycopg2.extensions.connection, vaga: dict) -> int | None:
    _validar_vaga(vaga)
    params = {
        "titulo": vaga["titulo"],
        "empresa": vaga["empresa"],
        "localizacao": vaga["localizacao"],
        "modalidade": vaga["modalidade"],
        "url": vaga["url"],
        "fonte": vaga["fonte"],
        "descricao": vaga.get("descricao"),
        "stack_detectada": vaga["stack_detectada"],
        "data_publicacao": vaga.get("data_publicacao"),
        "data_coleta": vaga["data_coleta"],
        "hash_unico": vaga["hash_unico"],
    }
    with conn.cursor() as cur:
        cur.execute(_INSERT_SQL, params)
        row = cur.fetchone()
    # commit aqui: uma linha em `vagas` significa "usuário já notificado" (data-model.md §3),
    # então a persistência precisa ser atômica com o INSERT que a produziu.
    conn.commit()
    return row[0] if row else None


def _validar_vaga(vaga: dict) -> None:
    # `stack_detectada` pode ser lista vazia e ainda ser válido (data-model.md §1), então a
    # checagem é por ausência da chave/None, não por "falsy" (uma lista [] é falsy em Python).
    faltando = [campo for campo in _CAMPOS_OBRIGATORIOS if campo not in vaga or vaga[campo] is None]
    if faltando:
        raise ValueError(
            f"Vaga não atende ao contrato (vaga.schema.json): campos obrigatórios ausentes {faltando}"
        )
    if vaga["modalidade"] not in _MODALIDADES_VALIDAS:
        raise ValueError(
            f"modalidade inválida: {vaga['modalidade']!r} (esperado um de {sorted(_MODALIDADES_VALIDAS)})"
        )
    if not _HASH_UNICO_RE.match(vaga["hash_unico"]):
        raise ValueError(
            f"hash_unico fora do formato esperado (64 caracteres hex): {vaga['hash_unico']!r}"
        )
