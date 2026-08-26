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


# --------------------------------------- filtro por grupos (acao + assunto)

@pytest.mark.parametrize(
    "titulo, esperado",
    [
        # titulos reais colhidos das fontes em 26/08/2026
        ("SEPLAG - AL publica edital de concurso público para Agente e Escrivão", True),
        ("Polícia Civil - BA abre concurso público para Delegado e Escrivão", True),
        ("CRF - ES abre concurso público para o cargo de Advogado", True),
        ("Exame Nacional da Magistratura abre inscrições para a 6ª edição", True),
        # itens de menu dos sites: tem o assunto, nao tem a acao
        ("Procuradoria-Geral de Justiça", False),
        ("Promotorias de Justiça nas cidades", False),
        ("Câmara de Pesquisa e Pós-Graduação CPP", False),
        # concurso real, mas de area que nao interessa
        ("Prefeitura abre concurso com vagas para Agente de Limpeza Urbana", False),
    ],
)
def test_grupos_separam_edital_de_item_de_menu(titulo, esperado):
    filtros = carregar().padroes["concurso"]
    item = Item(titulo, "https://exemplo.com/x", "f", "concurso")
    assert filtro.combina(item, filtros) is esperado


@pytest.mark.parametrize(
    "titulo, esperado",
    [
        ("Edital 12/2026 - Seleção de Mestrado em Direito", True),
        ("Inscrições abertas para o Programa de Pós-Graduação em Direito", True),
        ("Programas de Pós-Graduação", False),        # menu
        ("Editais de Seleção", False),                # menu: sem o assunto
        ("Gestão da pós-graduação stricto sensu", False),
        ("Edital de especialização em gestão pública", False),  # lato sensu
    ],
)
def test_grupos_mestrado(titulo, esperado):
    filtros = carregar().padroes["mestrado"]
    item = Item(titulo, "https://exemplo.com/x", "f", "mestrado")
    assert filtro.combina(item, filtros) is esperado


# ------------------------------------- variaveis vazias vindas do Actions

def test_segredo_opcional_vazio_cai_no_padrao(monkeypatch):
    """O Actions define a variavel mesmo sem o segredo: ela chega como ""."""
    monkeypatch.setenv("SMTP_USUARIO", "eu@gmail.com")
    monkeypatch.setenv("SMTP_SENHA", "senha")
    monkeypatch.setenv("EMAIL_DESTINO", "eu@gmail.com")
    for opcional in ("SMTP_PORTA", "SMTP_SERVIDOR", "EMAIL_REMETENTE", "SMTP_SSL"):
        monkeypatch.setenv(opcional, "")

    config = ConfigEmail.do_ambiente()
    assert config.porta == 465
    assert config.servidor == "smtp.gmail.com"
    assert config.remetente == "eu@gmail.com"
    assert config.usar_ssl is True


def test_porta_invalida_da_erro_legivel(monkeypatch):
    monkeypatch.setenv("SMTP_USUARIO", "eu@gmail.com")
    monkeypatch.setenv("SMTP_SENHA", "senha")
    monkeypatch.setenv("EMAIL_DESTINO", "eu@gmail.com")
    monkeypatch.setenv("SMTP_PORTA", "quinhentos")
    with pytest.raises(RuntimeError, match="SMTP_PORTA invalida"):
        ConfigEmail.do_ambiente()


def test_destino_com_espacos_em_branco_e_ignorado(monkeypatch):
    monkeypatch.setenv("SMTP_USUARIO", "eu@gmail.com")
    monkeypatch.setenv("SMTP_SENHA", "senha")
    monkeypatch.setenv("EMAIL_DESTINO", " a@x.com , , b@x.com ")
    monkeypatch.delenv("SMTP_PORTA", raising=False)
    assert ConfigEmail.do_ambiente().destinatarios == ("a@x.com", "b@x.com")


# ------------------------------------------- formato da senha de app do Google

@pytest.mark.parametrize(
    "digitada, esperada",
    [
        # como o Google mostra na tela, que e como costuma ser copiada
        ("tniz ulym tqfv vwov", "tnizulymtqfvvwov"),
        ("ABCD EFGH IJKL MNOP", "ABCDEFGHIJKLMNOP"),
        # ja sem espacos: nao mexe
        ("tnizulymtqfvvwov", "tnizulymtqfvvwov"),
        # senha comum com espaco de proposito: preservada
        ("minha senha secreta", "minha senha secreta"),
        ("abc def ghi jkl", "abc def ghi jkl"),
    ],
)
def test_senha_de_app_com_espacos(monkeypatch, digitada, esperada):
    monkeypatch.setenv("SMTP_USUARIO", "eu@gmail.com")
    monkeypatch.setenv("EMAIL_DESTINO", "eu@gmail.com")
    monkeypatch.setenv("SMTP_SENHA", digitada)
    monkeypatch.delenv("SMTP_PORTA", raising=False)
    assert ConfigEmail.do_ambiente().senha == esperada


def test_resumo_nao_vaza_a_senha():
    from rastreador.notificacao import resumir

    config = ConfigEmail(
        servidor="smtp.gmail.com", porta=465, usuario="fulana@gmail.com",
        senha="tnizulymtqfvvwov", remetente="fulana@gmail.com",
        destinatarios=("fulana@gmail.com",), usar_ssl=True,
    )
    resumo = resumir(config)
    assert "tnizulymtqfvvwov" not in resumo
    assert "fulana@gmail.com" not in resumo
    assert "fu***@gmail.com" in resumo
    assert "16 caractere(s)" in resumo


# ------------------------------------------ gravacao so quando ha mudanca

def test_salvar_nao_reescreve_quando_nada_mudou(tmp_path):
    caminho = tmp_path / "vistos.json"
    estado = Estado(caminho)
    estado.registrar([item(1)])
    estado.salvar()
    antes = caminho.read_text(encoding="utf-8")

    # execucao seguinte sem novidade: nada a registrar, arquivo intacto
    recarregado = Estado(caminho)
    recarregado.registrar(recarregado.novos([item(1)]))
    recarregado.limpar_antigos()
    recarregado.salvar()
    assert caminho.read_text(encoding="utf-8") == antes


def test_salvar_grava_quando_aparece_item_novo(tmp_path):
    caminho = tmp_path / "vistos.json"
    estado = Estado(caminho)
    estado.registrar([item(1)])
    estado.salvar()
    antes = caminho.read_text(encoding="utf-8")

    seguinte = Estado(caminho)
    seguinte.registrar(seguinte.novos([item(2)]))
    seguinte.salvar()
    assert caminho.read_text(encoding="utf-8") != antes
    assert "https://x.com/2" in caminho.read_text(encoding="utf-8")


# --------------------------------------- acentuacao no texto que a pessoa le

def test_email_sai_com_acento_nas_duas_versoes():
    itens = [Item("Edital de mestrado", "https://a.com/1", "UFG", "mestrado")]
    config = ConfigEmail(
        servidor="smtp.gmail.com", porta=465, usuario="u@x.com", senha="s",
        remetente="u@x.com", destinatarios=("d@x.com",), usar_ssl=True,
    )
    mensagem = montar_mensagem(itens, config)

    texto = mensagem.get_body(("plain",)).get_content()
    html_ = mensagem.get_body(("html",)).get_content()
    for parte in (texto, html_):
        assert "pós-graduação" in parte
        assert "automático" in parte
        assert "pos-graduacao" not in parte

    assert "pós-graduação" in mensagem["Subject"]


# ------------------------------ acao vale so no titulo, nunca dentro da URL

@pytest.mark.parametrize(
    "titulo, url, esperado",
    [
        # casos reais que entravam por causa da URL, nao do titulo
        ("Cartilhas disponibilizadas pelas áreas do tribunal",
         "https://www.tjdft.jus.br/publicacoes/edicoes/manuais-e-cartilhas", False),
        ("Aplicado aos Juízes e Ofícios Judiciais",
         "https://www.tjdft.jus.br/publicacoes/provimentos/provimento-geral", False),
        # o anuncio de verdade traz a acao no proprio titulo
        ("SEPLAG - AL publica edital de concurso para Escrivão",
         "https://www.pciconcursos.com.br/noticias/seplag-al", True),
    ],
)
def test_acao_precisa_estar_no_titulo(titulo, url, esperado):
    filtros = carregar().padroes["concurso"]
    assert filtro.combina(Item(titulo, url, "f", "concurso"), filtros) is esperado


def test_assunto_ainda_pode_vir_da_url():
    """"Processo Seletivo 2026/2" so se sabe que e de pos-graduacao pela URL."""
    filtros = carregar().padroes["mestrado"]
    item = Item("Processo Seletivo 2026/2", "https://ppgd.unb.br/processo-seletivo", "f", "mestrado")
    assert filtro.combina(item, filtros)


# ------------------------------------- prefixo de link de pular-para-conteudo

@pytest.mark.parametrize(
    "bruto, limpo",
    [
        ("Ir para o conteúdo de: EDITAL DPG/UnB Nº 08/2026 – BOLSAS",
         "EDITAL DPG/UnB Nº 08/2026 – BOLSAS"),
        ("Ir para o conteudo de:  Processo Seletivo 2026/2", "Processo Seletivo 2026/2"),
        ("Ir para a página de: Editais", "Editais"),
        # nao mexe em titulo que so comeca parecido
        ("Ir e vir: novo edital", "Ir e vir: novo edital"),
        ("Edital de mestrado", "Edital de mestrado"),
    ],
)
def test_limpa_prefixo_de_acessibilidade(bruto, limpo):
    from rastreador.coletor import limpar_titulo

    assert limpar_titulo(bruto) == limpo
