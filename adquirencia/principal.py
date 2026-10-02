"""Ponto de entrada: python -m adquirencia [--arquivo caminho.xlsx]"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import planilha

BRASILIA = timezone(timedelta(hours=-3))


def gravar_atomico(arquivo: Path, conteudo: bytes) -> None:
    """Grava num temporario e troca, para nunca deixar a planilha pela metade."""
    tmp = arquivo.with_name(arquivo.name + ".tmp")
    tmp.write_bytes(conteudo)
    try:
        os.replace(tmp, arquivo)
    except PermissionError:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"ERRO: {arquivo.name} esta aberto no Excel. Feche e rode de novo.")


def executar(arquivo: Path, dias: int) -> int:
    from . import odbc

    novos = odbc.buscar(dias)
    if not novos:
        raise SystemExit("ERRO: a consulta nao retornou nenhum dia; planilha mantida como estava.")
    wb = planilha.abrir(arquivo.read_bytes() if arquivo.exists() else None)
    linhas = planilha.aplicar(wb, novos, datetime.now(BRASILIA).replace(tzinfo=None))
    gravar_atomico(arquivo, planilha.salvar(wb))
    print(f"{arquivo}: {len(linhas)} dias no historico ({len(novos)} atualizados)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Atualiza a aba Adquirencia")
    p.add_argument("--arquivo", type=Path, default=os.environ.get("ARQUIVO_XLSX"),
                   help="caminho do .xlsx (ou variavel ARQUIVO_XLSX)")
    p.add_argument("--dias", type=int, default=int(os.environ.get("JANELA_DIAS", "7")),
                   help="janela de reprocessamento em dias (corrige atrasos de carga)")
    args = p.parse_args(argv)
    if not args.arquivo:
        p.error("informe --arquivo ou defina ARQUIVO_XLSX")
    return executar(Path(args.arquivo), args.dias)


if __name__ == "__main__":
    sys.exit(main())
