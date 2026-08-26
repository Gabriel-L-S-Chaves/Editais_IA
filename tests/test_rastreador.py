from pathlib import Path

import pytest

from rastreador import filtro
from rastreador.coletor import Item, extrair_html, extrair_rss, normalizar_url
from rastreador.config import Filtros, Fonte, carregar
from rastreador.estado import Estado
from rastreador.notificacao import ConfigEmail, montar_assunto, montar_mensagem
from rastreador.texto import normalizar

FIXTURES = Path(__file__).parent / "fixtures"


def fonte(categoria="mestrado", tipo="html", url="https://prpg.ufg.br/"):
    config = carregar()
    return Fonte(
        nome="teste",
        url=url,
        tipo=tipo,
        categoria=categoria,
        filtros=config.padroes[categoria],
    )


# ---------------------------------------------------------------- texto/url

def test_normalizar_remove_acento_e_caixa():
    assert normalizar("Inscrições ABERTAS – Pós-Graduação") == "inscricoes abertas - pos-graduacao"


def test_normalizar_url_ignora_utm_e_barra_final():
    a = normalizar_url("https://Exemplo.com/edital/?utm_source=x#topo")
    b = normalizar_url("https://exemplo.com/edital")
    assert a == b


# ------------------------------------------------------------------ coletor

def test_extrai_links_html_descartando_lixo():
    html = (FIXTURES / "pagina_ufg.html").read_text(encoding="utf-8")
    itens = extrair_html(html, fonte())
    urls = [i.url for i in itens]
    assert "javascript:void(0)" not in " ".join(urls)
    assert all(u.startswith("http") for u in urls)
    # ancoras curtas ("Início", "Topo") sao descartadas
    assert not any(i.titulo in {"Início", "Topo"} for i in itens)


def test_links_relativos_viram_absolutos():
    html = (FIXTURES / "pagina_ufg.html").read_text(encoding="utf-8")
    itens = extrair_html(html, fonte())
    assert any(i.url.startswith("https://prpg.ufg.br/n/12345") for i in itens)


def test_extrai_rss():
    xml = (FIXTURES / "feed_concursos.xml").read_text(encoding="utf-8")
    itens = extrair_rss(xml, fonte(categoria="concurso", tipo="rss"))
    assert len(itens) == 3
    assert itens[0].url == "https://exemplo.com/tjdft-analista"


def test_rss_invalido_da_erro_claro():
    with pytest.raises(ValueError):
        extrair_rss("<<isto nao e xml", fonte(categoria="concurso", tipo="rss"))


# ------------------------------------------------------------------- filtro

def test_filtro_mestrado_mantem_edital_e_descarta_resultado_e_evento():
    html = (FIXTURES / "pagina_ufg.html").read_text(encoding="utf-8")
    f = fonte()
    titulos = [i.titulo for i in filtro.filtrar(extrair_html(html, f), f.filtros)]
    assert any("Mestrado em Direito Agrário" in t for t in titulos)
    assert not any("Resultado final" in t for t in titulos)
    assert not any("boas-vindas" in t for t in titulos)


def test_filtro_concurso_so_deixa_passar_vaga_juridica():
    xml = (FIXTURES / "feed_concursos.xml").read_text(encoding="utf-8")
    f = fonte(categoria="concurso", tipo="rss")
    titulos = [i.titulo for i in filtro.filtrar(extrair_rss(xml, f), f.filtros)]
    assert any("Analista Judiciário" in t for t in titulos)
    assert not any("Limpeza Urbana" in t for t in titulos)
    assert not any("Gabarito" in t for t in titulos)  # excluido apesar de citar Procurador


def test_filtro_todas_exige_todos_os_termos():
    item = Item("Edital de mestrado em direito", "https://x.com/a", "f", "mestrado")
    assert filtro.combina(item, Filtros(todas=("edital", "direito")))
    assert not filtro.combina(item, Filtros(todas=("edital", "doutorado")))


# ------------------------------------------------------------------- estado

def item(n):
    return Item(f"Edital numero {n} de mestrado", f"https://x.com/{n}", "f", "mestrado")


def test_estado_so_devolve_ineditos(tmp_path):
    estado = Estado(tmp_path / "vistos.json")
    assert len(estado.novos([item(1), item(2)])) == 2
    estado.registrar([item(1)])
    estado.salvar()

    recarregado = Estado(tmp_path / "vistos.json")
    novos = recarregado.novos([item(1), item(2)])
    assert [i.url for i in novos] == ["https://x.com/2"]


def test_estado_deduplica_dentro_da_mesma_execucao(tmp_path):
    estado = Estado(tmp_path / "vistos.json")
    assert len(estado.novos([item(1), item(1)])) == 1


def test_mesma_url_com_utm_nao_avisa_duas_vezes(tmp_path):
    estado = Estado(tmp_path / "vistos.json")
    a = Item("Edital de mestrado 2026", "https://x.com/e", "f", "mestrado")
    b = Item("Edital de mestrado 2026", "https://x.com/e/?utm_source=rss", "f", "mestrado")
    estado.registrar([a])
    assert estado.novos([b]) == []


def test_estado_corrompido_nao_derruba(tmp_path):
    caminho = tmp_path / "vistos.json"
    caminho.write_text("{ nao e json", encoding="utf-8")
    assert Estado(caminho).itens == {}


def test_limpar_antigos(tmp_path):
    caminho = tmp_path / "vistos.json"
    estado = Estado(caminho)
    estado.itens = {
        "velho": {"visto_em": "2020-01-01T00:00:00+00:00"},
        "novo": {"visto_em": "2999-01-01T00:00:00+00:00"},
    }
    assert estado.limpar_antigos(dias=30) == 1
    assert "novo" in estado.itens


# --------------------------------------------------------------------- email

def test_assunto_e_corpo_agrupam_por_categoria():
    itens = [
        Item("Edital de mestrado em Direito", "https://a.com/1", "UFG", "mestrado"),
        Item("Concurso TJDFT analista judiciario", "https://b.com/2", "PCI", "concurso"),
    ]
    assunto = montar_assunto(itens)
    assert "2 novidade(s)" in assunto

    config = ConfigEmail(
        servidor="smtp.teste", porta=465, usuario="u", senha="s",
        remetente="u@teste", destinatarios=("d@teste",), usar_ssl=True,
    )
    mensagem = montar_mensagem(itens, config)
    corpo = mensagem.get_body(("plain",)).get_content()
    assert "https://a.com/1" in corpo and "https://b.com/2" in corpo
    assert mensagem.get_body(("html",)) is not None


def test_config_email_reclama_de_variavel_faltando(monkeypatch):
    for nome in ("SMTP_USUARIO", "SMTP_SENHA", "EMAIL_DESTINO"):
        monkeypatch.delenv(nome, raising=False)
    with pytest.raises(RuntimeError, match="SMTP_USUARIO"):
        ConfigEmail.do_ambiente()


# --------------------------------------------------------------------- config

def test_fontes_yml_carrega_e_tem_as_duas_categorias():
    config = carregar()
    categorias = {f.categoria for f in config.ativas}
    assert {"mestrado", "concurso"} <= categorias
    assert all(f.url.startswith("http") for f in config.fontes)
