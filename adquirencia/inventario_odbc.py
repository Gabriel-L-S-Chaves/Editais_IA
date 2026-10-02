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


def _colunas(cur, cat, schema):
    """(schema, tabela, coluna, tipo). Tenta information_schema; se o driver
    falhar, cai para SHOW/DESCRIBE."""
    filtro = f"AND table_schema = '{schema}'" if schema else ""
    try:
        cur.execute(
            f"SELECT CAST(table_schema AS STRING), CAST(table_name AS STRING), "
            f"CAST(column_name AS STRING), CAST(data_type AS STRING) "
            f"FROM {cat}.information_schema.columns "
            f"WHERE table_schema <> 'information_schema' {filtro} "
            f"ORDER BY 1,2,ordinal_position")
        return [tuple(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"[{cat}] information_schema falhou ({e}); usando SHOW/DESCRIBE")
    saida = []
    schemas = [schema] if schema else [r[0] for r in cur.execute(f"SHOW SCHEMAS IN {cat}").fetchall()]
    for sch in schemas:
        if sch == "information_schema":
            continue
        for r in cur.execute(f"SHOW TABLES IN {cat}.{sch}").fetchall():
            tab = r[1]
            try:
                for c in cur.execute(f"DESCRIBE TABLE {cat}.{sch}.{tab}").fetchall():
                    if not c[0] or c[0].startswith("#"):
                        break  # fim das colunas (comeca info de particao)
                    saida.append((sch, tab, c[0], c[1]))
            except Exception as e:
                print(f"[sem colunas] {cat}.{sch}.{tab}: {e}")
    return saida


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dsn", required=True)
    p.add_argument("--catalogo", nargs="+", help="ex.: gold silver (padrao: todos que voce enxerga)")
    p.add_argument("--schema", help="ex.: adquirencia (vale para todos os catalogos; omita para listar todos)")
    p.add_argument("--amostra", type=int, default=5)
    p.add_argument("--mascarar", action="store_true")
    a = p.parse_args()

    con = conectar(a.dsn)
    cur = con.cursor()
    catalogos = a.catalogo or [r[0] for r in cur.execute("SHOW CATALOGS").fetchall()]

    with open("inventario_colunas.csv", "w", newline="", encoding="utf-8-sig") as fc, \
         open("inventario_amostras.csv", "w", newline="", encoding="utf-8-sig") as fa:
        colunas, amostras = csv.writer(fc, delimiter=";"), csv.writer(fa, delimiter=";")
        colunas.writerow(["catalogo", "schema", "tabela", "coluna", "tipo"])
        amostras.writerow(["tabela", "linha", "colunas...(coluna=valor)"])
        for cat in catalogos:
            if cat in ("system", "samples", "hive_metastore"):
                continue
            try:
                tabelas = _colunas(cur, cat, a.schema)
            except Exception as e:  # sem permissao no catalogo: segue
                print(f"[pulado] {cat}: {e}")
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
                    print(f"[sem amostra] {nome}: {e}")
            print(f"{cat}: {len(vistas)} tabelas")
    print("Gerados: inventario_colunas.csv e inventario_amostras.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
