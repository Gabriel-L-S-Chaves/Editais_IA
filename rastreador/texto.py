"""Normalizacao de texto para comparacao de palavras-chave."""

from __future__ import annotations

import re
import unicodedata

_ESPACOS = re.compile(r"\s+")


def normalizar(texto: str) -> str:
    """Minusculas, sem acentos e com espacos colapsados.

    'Inscricoes Abertas - Pos-Graduacao' e 'inscrições abertas – pós-graduação'
    viram a mesma string, o que evita depender de como o site escreveu.
    """
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace("–", "-").replace("—", "-").replace(" ", " ")
    return _ESPACOS.sub(" ", texto).strip().lower()
