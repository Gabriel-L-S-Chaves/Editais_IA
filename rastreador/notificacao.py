"""Montagem e envio do e-mail de aviso."""

from __future__ import annotations

import html
import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate

from .coletor import Item

log = logging.getLogger(__name__)

ROTULOS = {
    "mestrado": "Mestrado / pos-graduacao",
    "concurso": "Concursos - Direito",
    "geral": "Outros",
}


@dataclass(frozen=True)
class ConfigEmail:
    servidor: str
    porta: int
    usuario: str
    senha: str
    remetente: str
    destinatarios: tuple[str, ...]
    usar_ssl: bool

    @classmethod
    def do_ambiente(cls) -> "ConfigEmail":
        faltando = [
            nome
            for nome in ("SMTP_USUARIO", "SMTP_SENHA", "EMAIL_DESTINO")
            if not os.environ.get(nome)
        ]
        if faltando:
            raise RuntimeError(
                "Variaveis de ambiente ausentes: " + ", ".join(faltando)
            )

        porta = int(os.environ.get("SMTP_PORTA", "465"))
        usuario = os.environ["SMTP_USUARIO"]
        destinos = tuple(
            e.strip() for e in os.environ["EMAIL_DESTINO"].split(",") if e.strip()
        )
        return cls(
            servidor=os.environ.get("SMTP_SERVIDOR", "smtp.gmail.com"),
            porta=porta,
            usuario=usuario,
            senha=os.environ["SMTP_SENHA"],
            remetente=os.environ.get("EMAIL_REMETENTE", usuario),
            destinatarios=destinos,
            usar_ssl=os.environ.get("SMTP_SSL", "auto").lower() in {"auto", "1", "true"}
            and porta == 465,
        )


def agrupar(itens: list[Item]) -> dict[str, list[Item]]:
    grupos: dict[str, list[Item]] = {}
    for item in itens:
        grupos.setdefault(item.categoria, []).append(item)
    for lista in grupos.values():
        lista.sort(key=lambda i: (i.fonte, i.titulo))
    return grupos


def montar_assunto(itens: list[Item]) -> str:
    grupos = agrupar(itens)
    partes = [f"{len(v)} {ROTULOS.get(k, k)}" for k, v in sorted(grupos.items())]
    return f"[Editais] {len(itens)} novidade(s): " + " | ".join(partes)


def montar_texto(itens: list[Item]) -> str:
    linhas = ["Novidades encontradas pelo rastreador de editais:", ""]
    for categoria, lista in sorted(agrupar(itens).items()):
        linhas.append(f"== {ROTULOS.get(categoria, categoria)} ({len(lista)}) ==")
        for item in lista:
            linhas.append(f"- {item.titulo}")
            linhas.append(f"  {item.url}")
            linhas.append(f"  fonte: {item.fonte}")
        linhas.append("")
    linhas.append(
        "Este e um aviso automatico. Confirme sempre a informacao na pagina oficial."
    )
    return "\n".join(linhas)


def montar_html(itens: list[Item]) -> str:
    blocos = [
        "<html><body style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;"
        "line-height:1.5;color:#1a1a1a\">",
        "<h2 style=\"margin:0 0 16px\">Novidades do rastreador de editais</h2>",
    ]
    for categoria, lista in sorted(agrupar(itens).items()):
        blocos.append(
            f"<h3 style=\"margin:24px 0 8px\">{html.escape(ROTULOS.get(categoria, categoria))}"
            f" <span style=\"font-weight:400;color:#666\">({len(lista)})</span></h3>"
        )
        blocos.append("<ul style=\"padding-left:18px;margin:0\">")
        for item in lista:
            blocos.append(
                "<li style=\"margin-bottom:10px\">"
                f"<a href=\"{html.escape(item.url, quote=True)}\">{html.escape(item.titulo)}</a>"
                f"<br><span style=\"color:#666;font-size:12px\">{html.escape(item.fonte)}</span>"
                "</li>"
            )
        blocos.append("</ul>")
    blocos.append(
        "<p style=\"color:#666;font-size:12px;margin-top:24px\">Aviso automatico. "
        "Confirme sempre a informacao na pagina oficial antes de se inscrever.</p>"
    )
    blocos.append("</body></html>")
    return "".join(blocos)


def montar_mensagem(itens: list[Item], config: ConfigEmail) -> EmailMessage:
    mensagem = EmailMessage()
    mensagem["Subject"] = montar_assunto(itens)
    mensagem["From"] = config.remetente
    mensagem["To"] = ", ".join(config.destinatarios)
    mensagem["Date"] = formatdate(localtime=True)
    mensagem.set_content(montar_texto(itens))
    mensagem.add_alternative(montar_html(itens), subtype="html")
    return mensagem


def enviar(itens: list[Item], config: ConfigEmail | None = None) -> None:
    if not itens:
        return
    config = config or ConfigEmail.do_ambiente()
    mensagem = montar_mensagem(itens, config)

    if config.usar_ssl:
        with smtplib.SMTP_SSL(config.servidor, config.porta, timeout=60) as smtp:
            smtp.login(config.usuario, config.senha)
            smtp.send_message(mensagem)
    else:
        with smtplib.SMTP(config.servidor, config.porta, timeout=60) as smtp:
            smtp.starttls()
            smtp.login(config.usuario, config.senha)
            smtp.send_message(mensagem)

    log.info("E-mail enviado para %s", ", ".join(config.destinatarios))
