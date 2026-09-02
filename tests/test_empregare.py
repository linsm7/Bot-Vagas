"""Testes determinísticos de scrapers/empregare.py (Artigo IX): parsing da resposta da API
pública, sem rede real (fixtures locais).

Rodar com: python -m unittest tests.test_empregare -v  (a partir da raiz do repo)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers import empregare


def _dado(**overrides) -> dict:
    base = {
        "id": 172486,
        "url": "vaga-desenvolvedor-mobile-react-native_172486",
        "titulo": "Desenvolvedor Mobile (React Native)",
        "chamada": "Buscamos pessoa desenvolvedora para atuar com React Native...",
        "timestamp": 1788270152,
        "empresa": "Acme Tecnologia",
        "trabalhoRemoto": "TotalmenteRemoto",
        "trabalhoRemotoTexto": "Totalmente Remoto",
        "cidades": ["Totalmente Remoto"],
    }
    base.update(overrides)
    return base


class TestModalidadeDeRotulo(unittest.TestCase):
    def test_totalmente_remoto_vira_remoto(self) -> None:
        self.assertEqual(empregare._modalidade_de_rotulo("Totalmente Remoto"), "remoto")

    def test_hibrido_vira_hibrido(self) -> None:
        self.assertEqual(empregare._modalidade_de_rotulo("Híbrido"), "hibrido")

    def test_presencial_vira_presencial(self) -> None:
        self.assertEqual(empregare._modalidade_de_rotulo("Presencial"), "presencial")

    def test_rotulo_desconhecido_ou_ausente_vira_none(self) -> None:
        self.assertIsNone(empregare._modalidade_de_rotulo("Não Informado"))
        self.assertIsNone(empregare._modalidade_de_rotulo(None))
        self.assertIsNone(empregare._modalidade_de_rotulo(""))


class TestExtrairVaga(unittest.TestCase):
    def test_vaga_remota_e_extraida_corretamente(self) -> None:
        vaga = empregare._extrair_vaga(_dado())
        assert vaga is not None
        self.assertEqual(vaga["titulo"], "Desenvolvedor Mobile (React Native)")
        self.assertEqual(vaga["empresa"], "Acme Tecnologia")
        self.assertEqual(vaga["modalidade"], "remoto")
        self.assertEqual(vaga["localizacao"], "Totalmente Remoto")
        self.assertEqual(
            vaga["url"],
            "https://www.empregare.com/pt-br/vaga-desenvolvedor-mobile-react-native_172486",
        )
        self.assertEqual(vaga["fonte"], "empregare")
        # `chamada` é só teaser — não deve ser usada como `descricao`.
        self.assertIsNone(vaga["descricao"])
        self.assertEqual(vaga["data_publicacao"].isoformat(), "2026-09-01")

    def test_vaga_presencial_em_brasilia_monta_localizacao_da_lista_de_cidades(self) -> None:
        vaga = empregare._extrair_vaga(
            _dado(
                trabalhoRemoto="Presencial",
                trabalhoRemotoTexto="Presencial",
                cidades=["Brasília, DF, BR"],
            )
        )
        assert vaga is not None
        self.assertEqual(vaga["modalidade"], "presencial")
        self.assertEqual(vaga["localizacao"], "Brasília, DF, BR")

    def test_sem_titulo_e_descartada(self) -> None:
        self.assertIsNone(empregare._extrair_vaga(_dado(titulo="")))

    def test_sem_empresa_e_descartada(self) -> None:
        self.assertIsNone(empregare._extrair_vaga(_dado(empresa="")))

    def test_sem_slug_de_url_e_descartada(self) -> None:
        self.assertIsNone(empregare._extrair_vaga(_dado(url="")))

    def test_timestamp_ausente_vira_data_publicacao_none(self) -> None:
        vaga = empregare._extrair_vaga(_dado(timestamp=None))
        assert vaga is not None
        self.assertIsNone(vaga["data_publicacao"])

    def test_sem_cidades_cai_para_brasil(self) -> None:
        self.assertEqual(empregare._montar_localizacao({"cidades": []}), "Brasil")
        self.assertEqual(empregare._montar_localizacao({}), "Brasil")


if __name__ == "__main__":
    unittest.main()
