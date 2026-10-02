"""Calculo das metricas a partir do historico diario."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class Dia:
    data: date
    faturamento: Decimal
    qtd_transacoes: int


@dataclass
class LinhaCalculada:
    data: date
    faturamento: Decimal
    qtd_transacoes: int
    ticket_medio: Decimal
    semana: str  # ISO, ex.: 2026-W40 (segunda a domingo)
    faturamento_semana: Decimal  # acumulado da semana ate o dia
    maior_ticket_medio: Decimal  # recorde historico ate o dia
    maior_faturamento_semana: Decimal  # recorde historico do acumulado semanal ate o dia


def _ticket(faturamento: Decimal, qtd: int) -> Decimal:
    return (faturamento / qtd).quantize(Decimal("0.01")) if qtd else Decimal("0.00")


def _semana(d: date) -> str:
    ano, semana, _ = d.isocalendar()
    return f"{ano}-W{semana:02d}"


def calcular(dias: list[Dia]) -> list[LinhaCalculada]:
    """Recalcula tudo do zero a partir do historico (idempotente)."""
    linhas: list[LinhaCalculada] = []
    acumulado: dict[str, Decimal] = {}
    maior_ticket = Decimal("0.00")
    maior_semana = Decimal("0.00")
    for dia in sorted(dias, key=lambda x: x.data):
        semana = _semana(dia.data)
        acumulado[semana] = acumulado.get(semana, Decimal("0")) + dia.faturamento
        ticket = _ticket(dia.faturamento, dia.qtd_transacoes)
        maior_ticket = max(maior_ticket, ticket)
        maior_semana = max(maior_semana, acumulado[semana])
        linhas.append(
            LinhaCalculada(
                data=dia.data,
                faturamento=dia.faturamento,
                qtd_transacoes=dia.qtd_transacoes,
                ticket_medio=ticket,
                semana=semana,
                faturamento_semana=acumulado[semana],
                maior_ticket_medio=maior_ticket,
                maior_faturamento_semana=maior_semana,
            )
        )
    return linhas
