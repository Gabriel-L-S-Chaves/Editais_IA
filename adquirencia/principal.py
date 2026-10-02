"""Ponto de entrada: python -m adquirencia"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import planilha
from .onedrive import ConflitoDeVersao, OneDrive

BRASILIA = timezone(timedelta(hours=-3))
TENTATIVAS = 3


def _buscar(dias: int):
    from . import databricks

    return databricks.buscar(dias)


def executar_local(arquivo: Path, dias: int) -> int:
    wb = planilha.abrir(arquivo.read_bytes() if arquivo.exists() else None)
    linhas = planilha.aplicar(wb, _buscar(dias), datetime.now(BRASILIA).replace(tzinfo=None))
    arquivo.write_bytes(planilha.salvar(wb))
    print(f"{arquivo}: {len(linhas)} dias no historico")
    return 0


def executar_onedrive(dias: int) -> int:
    drive = OneDrive(os.environ["ONEDRIVE_DRIVE_ID"], os.environ["ONEDRIVE_CAMINHO"])
    novos = _buscar(dias)  # consulta uma vez; so a gravacao e repetida em conflito
    for tentativa in range(1, TENTATIVAS + 1):
        atual = drive.baixar()
        wb = planilha.abrir(atual.conteudo)
        linhas = planilha.aplicar(wb, novos, datetime.now(BRASILIA).replace(tzinfo=None))
        try:
            drive.enviar(planilha.salvar(wb), atual.etag)
        except ConflitoDeVersao:
            print(f"planilha alterada durante a execucao (tentativa {tentativa}/{TENTATIVAS})")
            continue
        print(f"OneDrive atualizado: {len(linhas)} dias no historico")
        return 0
    print("ERRO: nao foi possivel gravar, planilha em edicao constante", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Atualiza a aba Adquirencia")
    p.add_argument("--dias", type=int, default=int(os.environ.get("JANELA_DIAS", "7")),
                   help="janela de reprocessamento em dias (corrige atrasos de carga)")
    p.add_argument("--arquivo", type=Path, help="grava em um .xlsx local em vez do OneDrive")
    args = p.parse_args(argv)
    return executar_local(args.arquivo, args.dias) if args.arquivo else executar_onedrive(args.dias)


if __name__ == "__main__":
    sys.exit(main())
