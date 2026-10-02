"""Conexao ODBC (DSN do Windows) com o Databricks."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

from .metricas import Dia

CONSULTA = Path(__file__).with_name("consulta.sql")


def conectar(dsn: str | None = None):
    import pyodbc  # import tardio: so quem usa ODBC precisa do pyodbc

    # DSN guarda host, http path e token: nada de segredo no codigo.
    return pyodbc.connect(f"DSN={dsn or os.environ['ODBC_DSN']}", autocommit=True)


def buscar(dias: int) -> list[Dia]:
    # :dias e substituido por inteiro (int() impede qualquer injecao); evita
    # depender do suporte a parametros do driver ODBC.
    sql = CONSULTA.read_text(encoding="utf-8").replace(":dias", str(int(dias)))
    with conectar() as conexao:
        cursor = conexao.cursor()
        cursor.execute(sql)
        return [Dia(r.data, Decimal(str(r.faturamento)), int(r.qtd_transacoes)) for r in cursor.fetchall()]
