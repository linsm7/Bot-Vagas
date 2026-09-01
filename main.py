from __future__ import annotations

import logging
import os

from core import database, filters, normalizer, telegram
from scrapers import linkedin

_logger = logging.getLogger(__name__)


def _configurar_logging() -> None:
    nivel = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, nivel, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def executar_pipeline() -> dict:
    # Conexão aberta antes do scraping para falhar rápido se DATABASE_URL não estiver
    # configurada, em vez de gastar as requisições ao LinkedIn para descobrir isso só depois.
    conn = database.get_connection()
    try:
        vagas_brutas = linkedin.buscar_vagas()
        total_coletadas = len(vagas_brutas)
        _logger.info("Coletadas %d vagas brutas do LinkedIn", total_coletadas)

        # Etapa 1 — filtros baratos (spec.md §4, itens 2-4: stack, localização/modalidade,
        # recência), nenhum deles precisa da descrição completa da vaga. `filters.vaga_elegivel`
        # também cobre nível/inglês (itens 6-7), mas nesta chamada `vaga["descricao"]` ainda é
        # `None` (ver scrapers/linkedin.py::_extrair_vaga) — `filters.nivel_elegivel` e
        # `filters.ingles_exigido` tratam `descricao is None` como "ainda não verificável" e não
        # bloqueiam a vaga aqui (ver core/filters.py). Ou seja: esta chamada já teve os últimos
        # dois critérios avaliados "na prática", sem custo, e só bloqueia por eles depois da
        # segunda chamada logo abaixo, quando a descrição já foi buscada.
        candidatas = []
        for vaga_bruta in vagas_brutas:
            vaga = normalizer.normalizar_vaga(vaga_bruta)
            if filters.vaga_elegivel(vaga):
                candidatas.append(vaga)
        _logger.info(
            "%d de %d vagas coletadas passaram nos filtros baratos (stack/localização/recência)",
            len(candidatas),
            total_coletadas,
        )

        total_novas = 0
        total_elegiveis = 0
        total_notificadas = 0
        for vaga in candidatas:
            # Checagem de novidade ANTES de buscar a descrição completa: `hash_unico` não
            # depende de descrição (core/normalizer.py::calcular_hash_unico), então uma vaga já
            # notificada em execução anterior é descartada aqui, sem gastar uma requisição extra
            # ao LinkedIn só para verificar nível/inglês de algo que já seria pulado de qualquer
            # forma. Esta é a otimização de ordem exigida pela spec para as novas regras.
            if database.vaga_ja_existe(conn, vaga["hash_unico"]):
                continue
            total_novas += 1

            descricao_completa = linkedin.buscar_descricao_completa(vaga["url"])
            if descricao_completa is None:
                # Falha de rede/parsing ao buscar a página individual da vaga (já logada dentro
                # de linkedin.buscar_descricao_completa). Sem a descrição não dá para avaliar
                # nível/inglês com segurança, então a vaga é descartada *nesta* execução; como só
                # é gravada no banco depois de notificada, ela será tentada de novo na próxima.
                continue
            vaga["descricao"] = descricao_completa

            # Segunda chamada a `vaga_elegivel`: agora com a descrição completa preenchida, os
            # critérios de nível (spec.md §4 item 6) e inglês (item 7) são avaliados de verdade.
            # Os critérios já checados na etapa 1 (stack/localização/recência) são reavaliados
            # também, mas são puros/idempotentes — sem custo relevante nem efeito colateral.
            if not filters.vaga_elegivel(vaga):
                continue
            total_elegiveis += 1

            enviado = telegram.enviar_alerta(vaga)
            if not enviado:
                _logger.warning(
                    "Falha ao notificar '%s' (%s); será reprocessada na próxima execução",
                    vaga["titulo"],
                    vaga["url"],
                )
                continue

            # Registro só acontece após o envio confirmado (data-model.md §3 / plan.md §3):
            # uma linha em `vagas` é, por definição, prova de que o usuário foi notificado.
            database.inserir_vaga(conn, vaga)
            total_notificadas += 1
    finally:
        conn.close()

    resumo = {
        "coletadas": total_coletadas,
        "elegiveis": total_elegiveis,
        "novas": total_novas,
        "notificadas": total_notificadas,
    }
    _logger.info(
        "Resumo da execução: %d coletadas, %d elegíveis (após checagem de descrição), "
        "%d novas (não vistas antes), %d notificadas",
        resumo["coletadas"],
        resumo["elegiveis"],
        resumo["novas"],
        resumo["notificadas"],
    )
    return resumo


def main() -> None:
    _configurar_logging()
    executar_pipeline()


if __name__ == "__main__":
    main()
