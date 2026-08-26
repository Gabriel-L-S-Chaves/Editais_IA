"""Baixa cada fonte e extrai os itens candidatos (titulo + link)."""

from __future__ import annotations

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from .config import Fonte

log = logging.getLogger(__name__)

CABECALHOS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 rastreador-editais/1.0"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

TEMPO_LIMITE = 30
TITULO_MINIMO = 12  # descarta ancoras como "leia mais", ">>", "1", "topo"

_LIXO = re.compile(r"\s+")

# Links de pular-para-o-conteudo, que alguns sites (a UnB, por exemplo) poem
# antes do titulo de verdade: "Ir para o conteudo de: EDITAL DPG/UnB No 08/2026".
_PREFIXO_ACESSIBILIDADE = re.compile(
    r"^ir para (o |a )?(conte[uú]do|texto|p[aá]gina)( de| da| do)?\s*:?\s*",
    re.IGNORECASE,
)


def limpar_titulo(titulo: str) -> str:
    return _PREFIXO_ACESSIBILIDADE.sub("", _LIXO.sub(" ", titulo)).strip()


@dataclass(frozen=True)
class Item:
    """Um link candidato a virar aviso."""

    titulo: str
    url: str
    fonte: str
    categoria: str

    @property
    def id(self) -> str:
        """Identidade estavel do item: url normalizada + titulo."""
        base = f"{normalizar_url(self.url)}|{_LIXO.sub(' ', self.titulo).strip().lower()}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def normalizar_url(url: str) -> str:
    """Remove fragmento, parametros de rastreio e barra final."""
    partes = urlsplit(url)
    consulta = "&".join(
        p
        for p in partes.query.split("&")
        if p and not p.lower().startswith(("utm_", "fbclid=", "gclid="))
    )
    caminho = partes.path.rstrip("/") or "/"
    return urlunsplit((partes.scheme, partes.netloc.lower(), caminho, consulta, ""))


def baixar(url: str, sessao: requests.Session | None = None) -> str:
    cliente = sessao or requests
    resposta = cliente.get(url, headers=CABECALHOS, timeout=TEMPO_LIMITE)
    resposta.raise_for_status()
    if not resposta.encoding or resposta.encoding.lower() == "iso-8859-1":
        resposta.encoding = resposta.apparent_encoding or "utf-8"
    return resposta.text


def extrair_html(conteudo: str, fonte: Fonte) -> list[Item]:
    """Pega todos os <a href> da pagina, sem depender do layout do site."""
    sopa = BeautifulSoup(conteudo, "html.parser")
    itens: list[Item] = []
    vistos: set[str] = set()

    for ancora in sopa.find_all("a", href=True):
        href = ancora["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        titulo = limpar_titulo(ancora.get_text(" ", strip=True))
        if len(titulo) < TITULO_MINIMO:
            # links so com imagem/icone: tenta o title ou o alt da imagem
            imagem = ancora.find("img")
            titulo = (
                ancora.get("title")
                or (imagem.get("alt") if imagem else "")
                or titulo
            ).strip()
        if len(titulo) < TITULO_MINIMO:
            continue

        url = urljoin(fonte.url, href)
        if not url.startswith(("http://", "https://")):
            continue

        chave = normalizar_url(url)
        if chave in vistos:
            continue
        vistos.add(chave)

        itens.append(
            Item(titulo=titulo, url=url, fonte=fonte.nome, categoria=fonte.categoria)
        )

    return itens


def extrair_rss(conteudo: str, fonte: Fonte) -> list[Item]:
    """Le RSS 2.0 e Atom com a stdlib (sem dependencia extra)."""
    try:
        raiz = ET.fromstring(conteudo.encode("utf-8"))
    except ET.ParseError as erro:
        raise ValueError(f"feed invalido: {erro}") from erro

    atom = "{http://www.w3.org/2005/Atom}"
    itens: list[Item] = []

    for entrada in list(raiz.iter("item")) + list(raiz.iter(f"{atom}entry")):
        titulo_no = entrada.find("title")
        if titulo_no is None:
            titulo_no = entrada.find(f"{atom}title")
        titulo = (titulo_no.text or "").strip() if titulo_no is not None else ""

        url = ""
        link_no = entrada.find("link")
        if link_no is not None and (link_no.text or "").strip():
            url = link_no.text.strip()
        else:
            for alternativo in entrada.findall(f"{atom}link"):
                if alternativo.get("rel", "alternate") == "alternate":
                    url = alternativo.get("href", "")
                    break

        if not titulo or not url:
            continue

        itens.append(
            Item(
                titulo=limpar_titulo(titulo),
                url=urljoin(fonte.url, url),
                fonte=fonte.nome,
                categoria=fonte.categoria,
            )
        )

    return itens


def coletar(fonte: Fonte, sessao: requests.Session | None = None) -> list[Item]:
    conteudo = baixar(fonte.url, sessao=sessao)
    if fonte.tipo == "rss":
        return extrair_rss(conteudo, fonte)
    return extrair_html(conteudo, fonte)
