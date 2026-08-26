"""Decide quais itens coletados viram aviso."""

from __future__ import annotations

from .coletor import Item
from .config import Filtros
from .texto import normalizar


def combina(item: Item, filtros: Filtros) -> bool:
    """Aplica os filtros sobre o item.

    A maioria das regras olha titulo e URL juntos, porque a URL costuma dizer
    o assunto ("/ppgd/", "/concursos/"). Ja `grupos_no_titulo` olha so o
    titulo: casar por pedaco de palavra dentro da URL e frouxo demais para as
    palavras de acao.
    """
    titulo = normalizar(item.titulo)
    alvo = normalizar(f"{item.titulo} {item.url}")

    for termo in filtros.excluir:
        if normalizar(termo) in alvo:
            return False

    for termo in filtros.todas:
        if normalizar(termo) not in alvo:
            return False

    for grupo in filtros.grupos:
        if grupo and not any(normalizar(termo) in alvo for termo in grupo):
            return False

    for grupo in filtros.grupos_no_titulo:
        if grupo and not any(normalizar(termo) in titulo for termo in grupo):
            return False

    if not filtros.qualquer:
        return True

    return any(normalizar(termo) in alvo for termo in filtros.qualquer)


def filtrar(itens: list[Item], filtros: Filtros) -> list[Item]:
    return [item for item in itens if combina(item, filtros)]
