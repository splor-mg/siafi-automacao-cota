"""AMARRADO com zero a esquerda.

O pandas convertia '0308' em 308 ja na leitura, e a validacao contava 3
digitos. Desde que o minimo passou a 4 (commit 56c5bf0, 06/07/2026), todo
AMARRADO comecando com zero era reprovado mesmo digitado corretamente — a
planilha 2121-2026-0003 IPSM.xlsx caiu nisso em 29/09.
"""
from openpyxl import Workbook

from consolida import _digitos_digitados, _ler_planilha


def planilha(tmp_path, amarrados, cabecalho='AMARRADO'):
    wb = Workbook()
    ws = wb.active
    ws.append(['UO_COD', cabecalho])
    for a in amarrados:
        ws.append([2121, a])        # '0308' entra como TEXTO, igual ao Excel
    caminho = tmp_path / 'origem.xlsx'
    wb.save(caminho)
    return caminho


def test_leitura_preserva_o_zero_a_esquerda(tmp_path):
    df = _ler_planilha(planilha(tmp_path, ['0308', 9399]), sheet_name=0)

    assert list(df['AMARRADO']) == ['0308', '9399']


def test_leitura_acha_a_coluna_mesmo_com_espaco_no_cabecalho(tmp_path):
    """O codigo limpa os cabecalhos so depois de ler; o dtype tem que casar
    com o nome cru."""
    df = _ler_planilha(planilha(tmp_path, ['0308'], cabecalho='AMARRADO '),
                       sheet_name=0)

    assert list(df['AMARRADO ']) == ['0308']


def test_conta_os_digitos_como_foram_digitados():
    assert _digitos_digitados('0308') == 4
    assert _digitos_digitados('9399') == 4
    assert _digitos_digitados('308') == 3       # continua reprovando
    assert _digitos_digitados(' 0308 ') == 4


def test_numero_que_o_excel_guardou_como_float():
    assert _digitos_digitados('9399.0') == 4
    assert _digitos_digitados(9399.0) == 4
