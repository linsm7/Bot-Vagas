"""Testes determinísticos de scrapers/indeed.py (Artigo IX): montagem de URL de busca e parsing
de um card de resultado a partir de um fixture HTML local (mesma estrutura validada manualmente
contra br.indeed.com/jobs), sem rede real.

Rodar com: python -m unittest tests.test_indeed -v  (a partir da raiz do repo)
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers import indeed

_CARD_HTML = """
<div class="job_seen_beacon">
  <table>
    <tbody>
      <tr>
        <td class="resultContent">
          <h2 class="jobTitle">
            <a data-jk="abc123def456">
              <span title="Desenvolvedor(a) Fullstack Júnior">Desenvolvedor(a) Fullstack Júnior</span>
            </a>
          </h2>
          <span data-testid="company-name">South System</span>
          <div data-testid="text-location">Remoto</div>
        </td>
      </tr>
    </tbody>
  </table>
</div>
"""

_CARD_HTML_SEM_LOCALIZACAO = """
<div class="job_seen_beacon">
  <h2 class="jobTitle">
    <a data-jk="xyz789">
      <span title="Engenheiro de Software Pleno">Engenheiro de Software Pleno</span>
    </a>
  </h2>
  <span data-testid="company-name">Acme Ltda</span>
</div>
"""


class TestMontarUrlBusca(unittest.TestCase):
    def test_monta_url_com_termo_e_localidade(self) -> None:
        url = indeed._montar_url_busca("React", "Remoto")
        self.assertTrue(url.startswith("https://br.indeed.com/jobs?"))
        self.assertIn("q=React", url)
        self.assertIn("l=Remoto", url)


class TestExtrairVaga(unittest.TestCase):
    def test_extrai_titulo_empresa_localizacao_e_monta_url_com_job_key(self) -> None:
        card = BeautifulSoup(_CARD_HTML, "html.parser").select_one("div.job_seen_beacon")
        vaga = indeed._extrair_vaga(card, localidade_busca="Remoto")
        assert vaga is not None
        self.assertEqual(vaga["titulo"], "Desenvolvedor(a) Fullstack Júnior")
        self.assertEqual(vaga["empresa"], "South System")
        self.assertEqual(vaga["localizacao"], "Remoto")
        self.assertEqual(vaga["url"], "https://br.indeed.com/viewjob?jk=abc123def456")
        self.assertEqual(vaga["fonte"], "indeed")
        self.assertIsNone(vaga["modalidade"])
        self.assertIsNone(vaga["descricao"])
        self.assertEqual(vaga["_localidade_busca"], "Remoto")

    def test_sem_localizacao_no_card_usa_localidade_da_busca_como_fallback(self) -> None:
        card = BeautifulSoup(_CARD_HTML_SEM_LOCALIZACAO, "html.parser").select_one("div.job_seen_beacon")
        vaga = indeed._extrair_vaga(card, localidade_busca="Brasília")
        assert vaga is not None
        self.assertEqual(vaga["localizacao"], "Brasília")

    def test_card_sem_data_jk_e_descartado(self) -> None:
        html = '<div class="job_seen_beacon"><span data-testid="company-name">X</span></div>'
        card = BeautifulSoup(html, "html.parser").select_one("div.job_seen_beacon")
        self.assertIsNone(indeed._extrair_vaga(card, localidade_busca="Remoto"))

    def test_card_sem_empresa_e_descartado(self) -> None:
        html = """
        <div class="job_seen_beacon">
          <a data-jk="abc123"><span title="Dev">Dev</span></a>
        </div>
        """
        card = BeautifulSoup(html, "html.parser").select_one("div.job_seen_beacon")
        self.assertIsNone(indeed._extrair_vaga(card, localidade_busca="Remoto"))


if __name__ == "__main__":
    unittest.main()
