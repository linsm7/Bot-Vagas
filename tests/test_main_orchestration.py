"""Testes determinísticos da orquestração multi-provedor em main.py (Artigo IX): isolamento de
falha por provedor (Artigo IV) e o registro de provedores em si. Não cobre `executar_pipeline`
fim a fim (depende de banco/Telegram reais, fora do escopo de teste automatizado determinístico).

Rodar com: python -m unittest tests.test_main_orchestration -v  (a partir da raiz do repo)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main
from core.normalizer import calcular_hash_unico
from scrapers import empregare, gupy, indeed, linkedin


class _ProvedorFalho:
    FONTE = "falho"

    def buscar_vagas(self) -> list[dict]:
        raise RuntimeError("simulação de falha inesperada no scraper")

    def buscar_descricao_completa(self, url: str) -> str | None:
        raise RuntimeError("simulação de falha inesperada no scraper")


class _ProvedorOk:
    FONTE = "ok"

    def __init__(self, vagas: list[dict]) -> None:
        self._vagas = vagas

    def buscar_vagas(self) -> list[dict]:
        return self._vagas

    def buscar_descricao_completa(self, url: str) -> str | None:
        return "descrição"


class TestColetarVagasDeUmProvedor(unittest.TestCase):
    def test_provedor_que_levanta_excecao_nao_propaga_e_devolve_lista_vazia(self) -> None:
        resultado = main._coletar_vagas_de_um_provedor(_ProvedorFalho())
        self.assertEqual(resultado, [])

    def test_provedor_ok_devolve_suas_vagas_normalmente(self) -> None:
        vagas = [{"titulo": "Dev"}]
        resultado = main._coletar_vagas_de_um_provedor(_ProvedorOk(vagas))
        self.assertEqual(resultado, vagas)


class TestRegistroDeProvedores(unittest.TestCase):
    def test_os_quatro_provedores_estao_registrados_com_fonte_unica(self) -> None:
        self.assertEqual(len(main._PROVEDORES), 4)
        fontes = {provedor.FONTE for provedor in main._PROVEDORES}
        self.assertEqual(fontes, {"linkedin", "gupy", "indeed", "empregare"})

    def test_cada_provedor_expoe_o_contrato_minimo(self) -> None:
        for provedor in (linkedin, gupy, indeed, empregare):
            self.assertTrue(hasattr(provedor, "FONTE"))
            self.assertTrue(callable(provedor.buscar_vagas))
            self.assertTrue(callable(provedor.buscar_descricao_completa))


class TestDedupPorFonte(unittest.TestCase):
    def test_mesma_url_em_fontes_diferentes_gera_hash_unico_diferente(self) -> None:
        # Critério de aceite: "fonte" entra na chave de dedup (core/normalizer.py::
        # calcular_hash_unico), então a mesma vaga aparecendo em dois sites (URLs coincidentes
        # não deveriam acontecer na prática, mas o hash não pode depender só da URL) tem
        # namespace de dedup próprio por provedor.
        url = "https://exemplo.com/mesma-vaga"
        hashes = {provedor.FONTE: calcular_hash_unico(provedor.FONTE, url) for provedor in main._PROVEDORES}
        self.assertEqual(len(set(hashes.values())), len(hashes))


if __name__ == "__main__":
    unittest.main()
