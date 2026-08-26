"""Ponto de entrada: coleta, filtra, avisa e guarda o estado."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import requests

from . import coletor, filtro, notificacao
from .coletor import Item
from .config import Config, Fonte, carregar
from .estado import CAMINHO_PADRAO as ESTADO_PADRAO
from .estado import Estado

log = logging.getLogger("rastreador")


def _sessao() -> requests.Session:
    sessao = requests.Session()
    adaptador = requests.adapters.HTTPAdapter(max_retries=2)
    sessao.mount("https://", adaptador)
    sessao.mount("http://", adaptador)
    return sessao


def varrer(config: Config, sessao: requests.Session | None = None) -> tuple[list[Item], list[str]]:
    """Coleta e filtra todas as fontes ativas.

    Uma fonte fora do ar nao derruba a execucao: o erro e acumulado e devolvido
    junto com o que as demais fontes conseguiram trazer.
    """
    sessao = sessao or _sessao()
    encontrados: list[Item] = []
    falhas: list[str] = []

    for fonte in config.ativas:
        try:
            brutos = coletor.coletar(fonte, sessao=sessao)
        except Exception as erro:  # rede, HTTP, XML malformado...
            log.warning("Falha em '%s' (%s): %s", fonte.nome, fonte.url, erro)
            falhas.append(f"{fonte.nome}: {erro}")
            continue

        relevantes = filtro.filtrar(brutos, fonte.filtros)
        log.info(
            "%s: %d link(s), %d relevante(s)", fonte.nome, len(brutos), len(relevantes)
        )
        encontrados.extend(relevantes)

    return encontrados, falhas


def executar(
    caminho_config: Path | str | None = None,
    caminho_estado: Path | str | None = None,
    enviar_email: bool = True,
    marcar_tudo: bool = False,
) -> int:
    config = carregar(caminho_config) if caminho_config else carregar()
    estado = Estado(caminho_estado or ESTADO_PADRAO)

    encontrados, falhas = varrer(config)
    novos = estado.novos(encontrados)

    if marcar_tudo:
        # primeira execucao: registra o acervo atual sem inundar a caixa de entrada
        estado.registrar(novos)
        estado.limpar_antigos()
        estado.salvar()
        print(f"Base inicial criada com {len(novos)} item(ns). Nenhum e-mail enviado.")
        return 0

    print(f"{len(encontrados)} item(ns) relevante(s), {len(novos)} inedito(s).")
    for item in novos:
        print(f"  [{item.categoria}] {item.titulo} -> {item.url}")

    if novos and enviar_email:
        try:
            notificacao.enviar(novos)
        except Exception as erro:
            # nao registra os itens: assim a proxima execucao tenta avisar de novo
            log.error("Falha ao enviar e-mail: %s", erro)
            print(f"ERRO ao enviar e-mail: {erro}", file=sys.stderr)
            return 1

    estado.registrar(novos)
    removidos = estado.limpar_antigos()
    estado.salvar()
    if removidos:
        log.info("%d registro(s) antigo(s) removido(s) do estado.", removidos)

    if falhas:
        print(f"Fontes com problema ({len(falhas)}):", file=sys.stderr)
        for falha in falhas:
            print(f"  - {falha}", file=sys.stderr)

    return 0


def testar_fontes(caminho_config: Path | str | None = None, amostra: int = 0) -> int:
    """Diagnostico: mostra o que cada fonte devolve, sem tocar no estado.

    Com `amostra`, as fontes que nao renderam nada mostram os primeiros links
    crus da pagina. E assim que se descobre se a fonte esta vazia, se o site
    monta a lista por JavaScript, ou se os filtros e que estao apertados demais.
    """
    config = carregar(caminho_config) if caminho_config else carregar()
    sessao = _sessao()
    problemas = 0

    for fonte in config.fontes:
        marca = "on " if fonte.ativa else "off"
        if not fonte.ativa:
            print(f"[{marca}] {fonte.nome}: desligada")
            continue
        try:
            brutos = coletor.coletar(fonte, sessao=sessao)
        except Exception as erro:
            problemas += 1
            print(f"[ERRO] {fonte.nome}: {erro}")
            continue
        relevantes = filtro.filtrar(brutos, fonte.filtros)
        print(f"[{marca}] {fonte.nome}: {len(brutos)} link(s) -> {len(relevantes)} relevante(s)")
        for item in relevantes[:5]:
            print(f"        . {item.titulo[:90]}")
        if not relevantes and amostra:
            print("        (nada passou nos filtros; amostra do que a pagina tem:)")
            for item in brutos[:amostra]:
                print(f"        ~ {item.titulo[:90]}")

    return 1 if problemas else 0


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        prog="rastreador",
        description="Rastreia editais de mestrado (UFG/UnB) e concursos de Direito.",
    )
    analisador.add_argument("--config", help="caminho do fontes.yml")
    analisador.add_argument("--estado", help="caminho do arquivo de estado")
    analisador.add_argument(
        "--sem-email",
        action="store_true",
        help="apenas mostra as novidades no terminal",
    )
    analisador.add_argument(
        "--inicializar",
        action="store_true",
        help="marca tudo que existe hoje como ja visto (primeira execucao)",
    )
    analisador.add_argument(
        "--testar-fontes",
        action="store_true",
        help="verifica quais fontes respondem e quantos itens casam com os filtros",
    )
    analisador.add_argument(
        "--amostra",
        type=int,
        default=0,
        metavar="N",
        help="com --testar-fontes, mostra N links crus das fontes que nao renderam nada",
    )
    analisador.add_argument("-v", "--verboso", action="store_true")
    args = analisador.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verboso else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    if args.testar_fontes:
        return testar_fontes(args.config, amostra=args.amostra)

    return executar(
        caminho_config=args.config,
        caminho_estado=args.estado,
        enviar_email=not args.sem_email,
        marcar_tudo=args.inicializar,
    )


if __name__ == "__main__":
    raise SystemExit(main())
