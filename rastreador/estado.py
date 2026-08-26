"""Memoria do que ja foi avisado, para nao repetir e-mail."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .coletor import Item
from .config import RAIZ

CAMINHO_PADRAO = RAIZ / "estado" / "vistos.json"
VALIDADE_DIAS = 180


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class Estado:
    def __init__(self, caminho: Path | str = CAMINHO_PADRAO):
        self.caminho = Path(caminho)
        self.itens: dict[str, dict] = {}
        self._carregar()

    def _carregar(self) -> None:
        if not self.caminho.exists():
            return
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # arquivo corrompido: comeca do zero em vez de derrubar a execucao
            dados = {}
        self.itens = dados.get("itens", {}) if isinstance(dados, dict) else {}

    def conhece(self, item: Item) -> bool:
        return item.id in self.itens

    def novos(self, itens: list[Item]) -> list[Item]:
        """Itens ineditos, sem duplicar dentro da propria execucao."""
        resultado: list[Item] = []
        vistos_agora: set[str] = set()
        for item in itens:
            if item.id in vistos_agora or self.conhece(item):
                continue
            vistos_agora.add(item.id)
            resultado.append(item)
        return resultado

    def registrar(self, itens: list[Item]) -> None:
        carimbo = _agora().isoformat()
        for item in itens:
            self.itens[item.id] = {
                "titulo": item.titulo,
                "url": item.url,
                "fonte": item.fonte,
                "categoria": item.categoria,
                "visto_em": carimbo,
            }

    def limpar_antigos(self, dias: int = VALIDADE_DIAS) -> int:
        """Descarta registros velhos para o arquivo nao crescer sem limite."""
        corte = _agora() - timedelta(days=dias)
        removidos = []
        for chave, valor in self.itens.items():
            carimbo = valor.get("visto_em")
            if not carimbo:
                continue
            try:
                quando = datetime.fromisoformat(carimbo)
            except ValueError:
                continue
            if quando.tzinfo is None:
                quando = quando.replace(tzinfo=timezone.utc)
            if quando < corte:
                removidos.append(chave)
        for chave in removidos:
            del self.itens[chave]
        return len(removidos)

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        conteudo = {
            "atualizado_em": _agora().isoformat(),
            "itens": self.itens,
        }
        self.caminho.write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
