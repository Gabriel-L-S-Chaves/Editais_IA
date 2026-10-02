"""Consulta rapida somente-leitura: python -m adquirencia.consulta "SELECT ..." [--dsn databricks]"""

from __future__ import annotations

import argparse
import re

from .odbc import conectar

LEITURA = re.compile(r"^\s*(SELECT|WITH|DESCRIBE|SHOW)\b", re.IGNORECASE)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("sql")
    p.add_argument("--dsn", default="databricks")
    p.add_argument("--limite", type=int, default=50)
    a = p.parse_args()
    if not LEITURA.match(a.sql) or ";" in a.sql.strip().rstrip(";"):
        p.error("somente uma instrucao de leitura (SELECT/WITH/DESCRIBE/SHOW)")
    cur = conectar(a.dsn).cursor()
    cur.execute(a.sql)
    nomes = [d[0] for d in cur.description]
    linhas = cur.fetchmany(a.limite)
    larg = [max(len(n), *(len(str(l[i])) for l in linhas)) if linhas else len(n) for i, n in enumerate(nomes)]
    print(" | ".join(n.ljust(w) for n, w in zip(nomes, larg)))
    print("-+-".join("-" * w for w in larg))
    for l in linhas:
        print(" | ".join(str(v).ljust(w) for v, w in zip(l, larg)))
    print(f"({len(linhas)} linhas, limite {a.limite})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
