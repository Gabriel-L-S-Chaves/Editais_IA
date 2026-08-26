"""Leitura e validacao do fontes.yml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_PADRAO = RAIZ / "fontes.yml"


@dataclass(frozen=True)
class Filtros:
    qualquer: tuple[str, ...] = ()
    todas: tuple[str, ...] = ()
    excluir: tuple[str, ...] = ()
    # cada grupo e um "pelo menos um destes"; TODOS os grupos precisam casar.
    # e o que separa um edital de verdade ("Edital de selecao - Mestrado em
    # Direito") de um item de menu do site ("Programas de Pos-Graduacao").
    grupos: tuple[tuple[str, ...], ...] = ()
    # iguais aos grupos, mas comparados so com o titulo do link, sem a URL.
    # A URL casa por pedaco de palavra: "publica" casa com "/publicacoes/", e
    # foi assim que cartilhas do TJDFT entraram como concurso.
    grupos_no_titulo: tuple[tuple[str, ...], ...] = ()

    @classmethod
    def de_dict(cls, dados: dict[str, Any] | None) -> "Filtros":
        dados = dados or {}
        return cls(
            qualquer=tuple(dados.get("qualquer") or ()),
            todas=tuple(dados.get("todas") or ()),
            excluir=tuple(dados.get("excluir") or ()),
            grupos=tuple(tuple(g) for g in (dados.get("grupos") or ())),
            grupos_no_titulo=tuple(
                tuple(g) for g in (dados.get("grupos_no_titulo") or ())
            ),
        )


@dataclass(frozen=True)
class Fonte:
    nome: str
    url: str
    tipo: str
    categoria: str
    filtros: Filtros
    ativa: bool = True


@dataclass(frozen=True)
class Config:
    fontes: tuple[Fonte, ...] = ()
    padroes: dict[str, Filtros] = field(default_factory=dict)

    @property
    def ativas(self) -> tuple[Fonte, ...]:
        return tuple(f for f in self.fontes if f.ativa)


def carregar(caminho: Path | str = CAMINHO_PADRAO) -> Config:
    dados = yaml.safe_load(Path(caminho).read_text(encoding="utf-8")) or {}

    padroes = {
        categoria: Filtros.de_dict(valor)
        for categoria, valor in (dados.get("padroes") or {}).items()
    }

    fontes: list[Fonte] = []
    for i, bruta in enumerate(dados.get("fontes") or []):
        nome = bruta.get("nome") or f"fonte-{i}"
        url = bruta.get("url")
        if not url:
            raise ValueError(f"Fonte '{nome}' esta sem url em {caminho}")

        tipo = (bruta.get("tipo") or "html").lower()
        if tipo not in {"html", "rss"}:
            raise ValueError(f"Fonte '{nome}': tipo '{tipo}' invalido (use html ou rss)")

        categoria = bruta.get("categoria") or "geral"
        filtros = (
            Filtros.de_dict(bruta["filtros"])
            if bruta.get("filtros")
            else padroes.get(categoria, Filtros())
        )

        fontes.append(
            Fonte(
                nome=nome,
                url=url,
                tipo=tipo,
                categoria=categoria,
                filtros=filtros,
                ativa=bool(bruta.get("ativa", True)),
            )
        )

    return Config(fontes=tuple(fontes), padroes=padroes)
