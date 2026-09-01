"""Testes do que é determinístico em core/filters.py (Artigo IX da constituição).

Rodar com: python -m unittest tests.test_filters -v  (a partir da raiz do repo)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.filters import _modalidade_localizacao_elegivel


class TestModalidadeLocalizacaoElegivel(unittest.TestCase):
    def test_remoto_brasil_e_aceito(self) -> None:
        vaga = {"modalidade": "remoto", "localizacao": "Brasil"}
        self.assertTrue(_modalidade_localizacao_elegivel(vaga))

    def test_remoto_com_cidade_brasileira_e_aceito(self) -> None:
        vaga = {"modalidade": "remoto", "localizacao": "Remoto, São Paulo, Brasil"}
        self.assertTrue(_modalidade_localizacao_elegivel(vaga))

    def test_remoto_estados_unidos_e_rejeitado(self) -> None:
        vaga = {"modalidade": "remoto", "localizacao": "United States"}
        self.assertFalse(_modalidade_localizacao_elegivel(vaga))

    def test_remoto_pais_estrangeiro_em_portugues_e_rejeitado(self) -> None:
        vaga = {"modalidade": "remoto", "localizacao": "Remoto - Argentina"}
        self.assertFalse(_modalidade_localizacao_elegivel(vaga))

    def test_remoto_sem_localizacao_clara_e_aceito(self) -> None:
        vaga = {"modalidade": "remoto", "localizacao": "Remoto"}
        self.assertTrue(_modalidade_localizacao_elegivel(vaga))

    def test_remoto_localizacao_vazia_e_aceito(self) -> None:
        vaga = {"modalidade": "remoto", "localizacao": ""}
        self.assertTrue(_modalidade_localizacao_elegivel(vaga))

    def test_remoto_localizacao_ausente_e_aceito(self) -> None:
        vaga = {"modalidade": "remoto"}
        self.assertTrue(_modalidade_localizacao_elegivel(vaga))

    def test_remoto_nao_confunde_cidade_brasileira_com_pais_estrangeiro(self) -> None:
        # "Peruíbe" (litoral de SP) contém "peru" como substring — não pode ser confundido
        # com o país Peru.
        vaga = {"modalidade": "remoto", "localizacao": "Remoto, Peruíbe, SP, Brasil"}
        self.assertTrue(_modalidade_localizacao_elegivel(vaga))

    def test_presencial_brasilia_continua_aceito_sem_regressao(self) -> None:
        vaga = {"modalidade": "presencial", "localizacao": "Brasília, Distrito Federal, Brasil"}
        self.assertTrue(_modalidade_localizacao_elegivel(vaga))

    def test_presencial_fora_de_brasilia_goiania_continua_rejeitado(self) -> None:
        vaga = {"modalidade": "presencial", "localizacao": "São Paulo, SP, Brasil"}
        self.assertFalse(_modalidade_localizacao_elegivel(vaga))

    def test_hibrido_goiania_continua_aceito_sem_regressao(self) -> None:
        vaga = {"modalidade": "hibrido", "localizacao": "Goiânia, GO, Brasil"}
        self.assertTrue(_modalidade_localizacao_elegivel(vaga))

    def test_modalidade_desconhecida_e_rejeitada(self) -> None:
        vaga = {"modalidade": "outra", "localizacao": "Brasília, DF"}
        self.assertFalse(_modalidade_localizacao_elegivel(vaga))


if __name__ == "__main__":
    unittest.main()
