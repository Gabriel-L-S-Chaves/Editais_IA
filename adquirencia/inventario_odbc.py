"""Inventario do que o seu DSN enxerga: python -m adquirencia.inventario_odbc --dsn NOME

Gera inventario_colunas.csv e inventario_amostras.csv na pasta atual.
Use --catalogo/--schema para limitar, --mascarar para esconder valores de
colunas com nomes sensiveis (cnpj, cpf, nome, email...).
"""

from __future__ import annotations

import argparse
import csv

from .odbc import conectar

SENSIVEIS = ("cnpj", "cpf", "nome", "email", "telefone", "documento", "razao")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dsn", required=True)
    p.add_argument("--catalogo", help="ex.: gold (padrao: todos que voce enxerga)")
    p.add_argument("--schema", help="ex.: adquirencia")
    p.add_argument("--amostra", type=int, default=5)
    p.add_argument("--mascarar", action="store_true")
    a = p.parse_args()

    con = conectar(a.dsn)
    cur = con.cursor()
    catalogos = [a.catalogo] if a.catalogo else [r[0] for r in cur.execute("SHOW CATALOGS").fetchall()]

    with open("inventario_colunas.csv", "w", newline="", encoding="utf-8-sig") as fc, \
         open("inventario_amostras.csv", "w", newline="", encoding="utf-8-sig") as fa:
        colunas, amostras = csv.writer(fc, delimiter=";"), csv.writer(fa, delimiter=";")
        colunas.writerow(["catalogo", "schema", "tabela", "coluna", "tipo"])
        amostras.writerow(["tabela", "linha", "colunas...(coluna=valor)"])
        for cat in catalogos:
            if cat in ("system", "samples", "hive_metastore"):
                continue
            try:
                filtro = f"AND table_schema = '{a.schema}'" if a.schema else ""
                tabelas = cur.execute(
                    f"SELECT table_schema, table_name, column_name, data_type "
                    f"FROM {cat}.information_schema.columns "
                    f"WHERE table_schema <> 'information_schema' {filtro} "
                    f"ORDER BY 1,2,ordinal_position").fetchall()
            except Exception as e:  # sem permissao no catalogo: segue
                print(f"[pulado] {cat}: {str(e)[:100]}")
                continue
            vistas = []
            for sch, tab, col, tipo in tabelas:
                colunas.writerow([cat, sch, tab, col, tipo])
                if (sch, tab) not in vistas:
                    vistas.append((sch, tab))
            for sch, tab in vistas:
                nome = f"{cat}.{sch}.{tab}"
                try:
                    cur.execute(f"SELECT * FROM {nome} LIMIT {int(a.amostra)}")
                    nomes = [d[0] for d in cur.description]
                    for i, linha in enumerate(cur.fetchall(), 1):
                        amostras.writerow([nome, i] + [
                            f"{n}=***" if a.mascarar and any(s in n.lower() for s in SENSIVEIS) else f"{n}={v}"
                            for n, v in zip(nomes, linha)])
                except Exception as e:
                    print(f"[sem amostra] {nome}: {str(e)[:100]}")
            print(f"{cat}: {len(vistas)} tabelas")
    print("Gerados: inventario_colunas.csv e inventario_amostras.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
