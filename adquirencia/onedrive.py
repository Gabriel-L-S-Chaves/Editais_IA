"""Download/upload do .xlsx no OneDrive/SharePoint via Microsoft Graph.

Usa o fluxo client-credentials (app registrado no Entra ID com permissao
Files.ReadWrite.All/Sites.ReadWrite.All). O upload usa If-Match com o eTag lido
no download: se alguem salvou a planilha no meio da execucao, o Graph responde
412 e a rotina rele o arquivo e tenta de novo, em vez de sobrescrever.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote

import requests

GRAPH = "https://graph.microsoft.com/v1.0"


class ConflitoDeVersao(Exception):
    pass


@dataclass
class Arquivo:
    conteudo: bytes | None  # None: arquivo ainda nao existe
    etag: str | None


class OneDrive:
    def __init__(self, drive_id: str, caminho: str, sessao: requests.Session | None = None):
        self.caminho = caminho.strip("/")
        self.base = f"{GRAPH}/drives/{drive_id}/root:/{quote(self.caminho)}:"
        self.http = sessao or requests.Session()
        self.http.headers["Authorization"] = f"Bearer {self._token()}"

    @staticmethod
    def _token() -> str:
        r = requests.post(
            f"https://login.microsoftonline.com/{os.environ['AZURE_TENANT_ID']}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": os.environ["AZURE_CLIENT_ID"],
                "client_secret": os.environ["AZURE_CLIENT_SECRET"],
                "scope": "https://graph.microsoft.com/.default",
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["access_token"]

    def baixar(self) -> Arquivo:
        meta = self.http.get(self.base, timeout=30)
        if meta.status_code == 404:
            return Arquivo(None, None)
        meta.raise_for_status()
        conteudo = self.http.get(f"{self.base}/content", timeout=120)
        conteudo.raise_for_status()
        return Arquivo(conteudo.content, meta.json().get("eTag"))

    def enviar(self, conteudo: bytes, etag: str | None) -> None:
        # Upload simples (ate 250 MB). If-Match so quando o arquivo ja existia.
        cabecalhos = {"If-Match": etag} if etag else {"If-None-Match": "*"}
        r = self.http.put(f"{self.base}/content", data=conteudo, headers=cabecalhos, timeout=120)
        if r.status_code in (409, 412):
            raise ConflitoDeVersao(r.text)
        r.raise_for_status()
