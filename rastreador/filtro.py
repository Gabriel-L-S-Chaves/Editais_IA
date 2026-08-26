"""Decide quais itens coletados viram aviso."""

from __future__ import annotations

from .coletor import Item
from .config import Filtros
from .texto import normalizar


def combina(item: Item, filtros: Filtros) -> bool:
    """Aplica qualquer/todas/excluir sobre titulo + url do item."""
    alvo = normalizar(f"{item.titulo} {item.url}")

    for termo in filtros.excluir:
        if normalizar(termo) in alvo:
            return False

    for termo in filtros.todas:
        if normalizar(termo) not in alvo:
            return False

    if not filtros.qualquer:
        return True

    return any(normalizar(termo) in alvo for termo in filtros.qualquer)


def filtrar(itens: list[Item], filtros: Filtros) -> list[Item]:
    return [item for item in itens if combina(item, filtros)]
