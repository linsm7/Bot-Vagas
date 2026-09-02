from __future__ import annotations

from typing import Protocol


class Scraper(Protocol):
    """Interface comum a todo scraper de fonte (plan.md §4).

    Não é uma classe base para herdar — os scrapers (`scrapers/linkedin.py`,
    `scrapers/gupy.py`, `scrapers/indeed.py`, `scrapers/empregare.py`) continuam sendo módulos
    simples com funções soltas (duck typing, Artigo I da constituição — sem framework/abstração
    além do necessário). Este `Protocol` existe só para dar um tipo nomeado a `main.py` (a lista
    de provedores) e documentar num único lugar o contrato que os quatro módulos já seguem, sem
    forçar herança nem verificação em tempo de execução.
    """

    FONTE: str

    def buscar_vagas(self) -> list[dict]:
        """Busca vagas candidatas na fonte e as devolve como dicts (contrato em
        contracts/vaga-schema.md). Cada scraper trata suas próprias falhas de rede/parsing
        internamente e devolve `[]` nesses casos — nunca propaga a exceção (Artigo IV)."""
        ...

    def buscar_descricao_completa(self, url: str) -> str | None:
        """Busca a descrição completa de uma vaga já candidata (chamada só depois dos filtros
        baratos e da checagem de novidade — ver main.py::executar_pipeline).

        Retorno:
        - `str` (pode ser vazia) quando a busca/verificação foi bem-sucedida.
        - `None` quando não foi possível verificar (falha de rede ou parsing) — sinal para
          `main.py` descartar a vaga *nesta* execução, sem gravar no banco.
        """
        ...
