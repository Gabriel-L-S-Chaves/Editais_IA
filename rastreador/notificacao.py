"""Montagem e envio do e-mail de aviso."""

from __future__ import annotations

import html
import logging
import os
import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate

from .coletor import Item

log = logging.getLogger(__name__)

# Texto que a pessoa le no e-mail: aqui vai portugues com acento, ao contrario
# do resto do codigo.
ROTULOS = {
    "mestrado": "Mestrado / pós-graduação",
    "concurso": "Concursos — Direito",
    "geral": "Outros",
}


# Senha de app do Google: 16 letras que a tela mostra em 4 grupos de 4.
_SENHA_DE_APP = re.compile(r"^[a-z]{4}(?: [a-z]{4}){3}$", re.IGNORECASE)


def _limpar_senha(senha: str) -> str:
    """Tira os espacos quando a senha tem a cara de uma senha de app do Google.

    A tela do Google exibe "abcd efgh ijkl mnop" e e assim que ela costuma ser
    copiada, mas o valor real sao as 16 letras seguidas. So mexe quando o
    formato bate exatamente, para nao estragar a senha de quem usa espaco de
    proposito em outro provedor.
    """
    return senha.replace(" ", "") if _SENHA_DE_APP.match(senha) else senha


def _ambiente(nome: str, padrao: str = "") -> str:
    """Le uma variavel tratando string vazia como ausente.

    O GitHub Actions define toda variavel mapeada para um segredo, mesmo quando
    o segredo nao existe — ela chega como "". Sem isto, os.environ.get(nome,
    padrao) devolve "" em vez do padrao, e a porta vira int("").
    """
    return (os.environ.get(nome) or "").strip() or padrao


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
            if not _ambiente(nome)
        ]
        if faltando:
            raise RuntimeError(
                "Variaveis de ambiente ausentes: " + ", ".join(faltando)
            )

        bruta = _ambiente("SMTP_PORTA", "465")
        try:
            porta = int(bruta)
        except ValueError as erro:
            raise RuntimeError(f"SMTP_PORTA invalida: {bruta!r}") from erro

        usuario = _ambiente("SMTP_USUARIO")
        destinos = tuple(
            e.strip() for e in _ambiente("EMAIL_DESTINO").split(",") if e.strip()
        )
        return cls(
            servidor=_ambiente("SMTP_SERVIDOR", "smtp.gmail.com"),
            porta=porta,
            usuario=usuario,
            senha=_limpar_senha(_ambiente("SMTP_SENHA")),
            remetente=_ambiente("EMAIL_REMETENTE", usuario),
            destinatarios=destinos,
            usar_ssl=_ambiente("SMTP_SSL", "auto").lower() in {"auto", "1", "true"}
            and porta == 465,
        )


def mascarar(endereco: str) -> str:
    """an***@gmail.com — o bastante para conferir a conta sem expor o endereco."""
    if "@" not in endereco:
        return (endereco[:2] + "***") if endereco else "(vazio)"
    local, _, dominio = endereco.partition("@")
    return f"{local[:2]}***@{dominio}"


def resumir(config: "ConfigEmail") -> str:
    """Descreve a configuracao sem revelar a senha, so o tamanho dela.

    Uma senha de app do Google tem 16 caracteres. Qualquer outro numero aqui
    aponta o dedo para o segredo (letra faltando, texto colado errado); 16 com
    recusa do servidor aponta para a senha em si, que precisa ser regerada.
    """
    return (
        f"servidor={config.servidor}:{config.porta} ssl={config.usar_ssl} "
        f"usuario={mascarar(config.usuario)} "
        f"remetente={mascarar(config.remetente)} "
        f"destino={', '.join(mascarar(d) for d in config.destinatarios)} "
        f"tamanho da senha={len(config.senha)} caractere(s)"
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
        "Este é um aviso automático. Confirme sempre a informação na página "
        "oficial antes de se inscrever."
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
        "<p style=\"color:#666;font-size:12px;margin-top:24px\">Aviso automático. "
        "Confirme sempre a informação na página oficial antes de se inscrever.</p>"
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
