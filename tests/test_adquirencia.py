from datetime import date, datetime
from decimal import Decimal

from adquirencia import planilha
from adquirencia.metricas import Dia, calcular

AGORA = datetime(2026, 10, 2, 9, 0)


def dia(d, fat, qtd):
    return Dia(d, Decimal(str(fat)), qtd)


def test_ticket_e_recordes():
    linhas = calcular([
        dia(date(2026, 9, 28), 1000, 10),  # seg: ticket 100
        dia(date(2026, 9, 29), 3000, 10),  # ter: ticket 300, semana 4000
        dia(date(2026, 10, 5), 500, 10),   # seg seguinte: ticket 50, semana nova
    ])
    assert [l.ticket_medio for l in linhas] == [Decimal("100.00"), Decimal("300.00"), Decimal("50.00")]
    assert [l.faturamento_semana for l in linhas] == [Decimal("1000"), Decimal("4000"), Decimal("500")]
    # recordes nao caem quando o dia seguinte e pior
    assert linhas[2].maior_ticket_medio == Decimal("300.00")
    assert linhas[2].maior_faturamento_semana == Decimal("4000")


def test_sem_transacoes_nao_divide_por_zero():
    assert calcular([dia(date(2026, 10, 1), 0, 0)])[0].ticket_medio == Decimal("0.00")


def test_rodar_duas_vezes_nao_duplica_e_corrige_o_dia():
    wb = planilha.abrir(None)
    planilha.aplicar(wb, [dia(date(2026, 10, 1), 100, 1)], AGORA)
    planilha.aplicar(wb, [dia(date(2026, 10, 1), 250, 5)], AGORA)  # recarga corrigida
    ws = wb[planilha.ABA]
    assert ws.max_row == 2
    assert ws["B2"].value == 250 and ws["C2"].value == 5 and ws["D2"].value == 50


def test_preserva_historico_fora_da_janela_e_outras_abas():
    wb = planilha.abrir(None)
    planilha.aplicar(wb, [dia(date(2026, 9, 1), 100, 1)], AGORA)
    wb.create_sheet("Outra")["A1"] = "intocada"
    wb = planilha.abrir(planilha.salvar(wb))  # passa por bytes, como no OneDrive
    planilha.aplicar(wb, [dia(date(2026, 10, 1), 200, 2)], AGORA)
    assert sorted(planilha.ler_historico(wb)) == [date(2026, 9, 1), date(2026, 10, 1)]
    assert wb["Outra"]["A1"].value == "intocada"
    assert wb.sheetnames == [planilha.ABA, "Outra"]


def test_gravar_atomico_nao_deixa_temporario(tmp_path):
    from adquirencia.principal import gravar_atomico
    alvo = tmp_path / "r.xlsx"
    gravar_atomico(alvo, b"abc")
    assert alvo.read_bytes() == b"abc" and [f.name for f in tmp_path.iterdir()] == ["r.xlsx"]
