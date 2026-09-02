"""Testes determinísticos de scrapers/gupy.py (Artigo IX): parsing da resposta da API pública,
sem rede real (fixtures locais).

Rodar com: python -m unittest tests.test_gupy -v  (a partir da raiz do repo)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers import gupy


def _job(**overrides) -> dict:
    base = {
        "id": 12150336,
        "name": "Pessoa Desenvolvedora Fullstack React Pl (Remoto)",
        "description": "<p>Trabalhamos com <b>React</b> e TypeScript.&nbsp;</p>",
        "careerPageName": "Starian",
        "careerPageUrl": "https://starian.gupy.io/eyJzb3VyY2UiOiJndXB5X3BvcnRhbCJ9",
        "jobUrl": "https://starian.gupy.io/job/eyJqb2JJZCI6MTIxNTAzMzYsInNvdXJjZSI6Imd1cHlfcG9ydGFsIn0=",
        "publishedDate": "2026-08-27T21:05:31.885Z",
        "isRemoteWork": True,
        "city": "",
        "state": "",
        "country": "Brasil",
        "workplaceType": "remote",
    }
    base.update(overrides)
    return base


class TestExtrairVaga(unittest.TestCase):
    def test_vaga_remota_e_extraida_com_descricao_ja_completa(self) -> None:
        vaga = gupy._extrair_vaga(_job())
        assert vaga is not None
        self.assertEqual(vaga["titulo"], "Pessoa Desenvolvedora Fullstack React Pl (Remoto)")
        self.assertEqual(vaga["empresa"], "Starian")
        self.assertEqual(vaga["modalidade"], "remoto")
        # `country` vem preenchido ("Brasil") mesmo em vagas remotas na API real da Gupy — só
        # cai no rótulo "Remoto" (ver TestMontarLocalizacao) quando nem isso vem preenchido.
        self.assertEqual(vaga["localizacao"], "Brasil")
        self.assertEqual(vaga["fonte"], "gupy")
        # HTML foi convertido para texto puro (sem tags, sem entidades soltas). `get_text` com
        # separador de linha (mesmo padrão de scrapers/linkedin.py) quebra em cada fronteira de
        # tag inline, por isso "React" (dentro de <b>) fica em uma linha própria.
        self.assertEqual(vaga["descricao"], "Trabalhamos com\nReact\ne TypeScript.")
        self.assertIsNone(vaga["hash_unico"])
        self.assertEqual(vaga["data_publicacao"].isoformat(), "2026-08-27")

    def test_vaga_hibrida_monta_localizacao_a_partir_de_cidade_estado_pais(self) -> None:
        vaga = gupy._extrair_vaga(
            _job(workplaceType="hybrid", city="Brasília", state="Distrito Federal")
        )
        assert vaga is not None
        self.assertEqual(vaga["modalidade"], "hibrido")
        self.assertEqual(vaga["localizacao"], "Brasília, Distrito Federal, Brasil")

    def test_vaga_presencial_mapeia_on_site_para_presencial(self) -> None:
        vaga = gupy._extrair_vaga(_job(workplaceType="on-site", city="Goiânia", state="Goiás"))
        assert vaga is not None
        self.assertEqual(vaga["modalidade"], "presencial")

    def test_workplace_type_desconhecido_fica_none_para_normalizer_decidir(self) -> None:
        vaga = gupy._extrair_vaga(_job(workplaceType="algo-novo-nao-mapeado"))
        assert vaga is not None
        self.assertIsNone(vaga["modalidade"])

    def test_sem_titulo_e_descartada(self) -> None:
        self.assertIsNone(gupy._extrair_vaga(_job(name="")))

    def test_sem_url_e_descartada(self) -> None:
        self.assertIsNone(gupy._extrair_vaga(_job(jobUrl="")))

    def test_descricao_ausente_vira_string_vazia_nao_none(self) -> None:
        vaga = gupy._extrair_vaga(_job(description=None))
        assert vaga is not None
        self.assertEqual(vaga["descricao"], "")


class TestMontarLocalizacao(unittest.TestCase):
    def test_sem_nenhum_campo_e_remoto_vira_rotulo_remoto(self) -> None:
        self.assertEqual(
            gupy._montar_localizacao({"workplaceType": "remote", "city": "", "state": "", "country": ""}),
            "Remoto",
        )

    def test_sem_nenhum_campo_e_nao_remoto_cai_para_brasil(self) -> None:
        self.assertEqual(
            gupy._montar_localizacao({"workplaceType": "hybrid", "city": "", "state": "", "country": ""}),
            "Brasil",
        )


if __name__ == "__main__":
    unittest.main()
