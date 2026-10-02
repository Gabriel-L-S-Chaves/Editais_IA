"""Busca os totais diarios no Databricks (SQL warehouse)."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

from .metricas import Dia

CONSULTA = Path(__file__).with_name("consulta.sql")


def buscar(dias: int) -> list[Dia]:
    from databricks import sql  # import tardio: so quem consulta precisa do conector

    with sql.connect(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    ) as conexao, conexao.cursor() as cursor:
        cursor.execute(CONSULTA.read_text(encoding="utf-8"), {"dias": dias})
        return [
            Dia(r["data"], Decimal(str(r["faturamento"])), int(r["qtd_transacoes"]))
            for r in cursor.fetchall()
        ]
