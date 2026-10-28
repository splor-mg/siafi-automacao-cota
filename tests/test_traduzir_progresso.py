"""So '0011-REGISTRO EFETUADO' vira 'Ok' na coluna Progresso.

Em 28/10/2026 o SIAFI devolveu 'Z03-SIAFI INDISPONIVEL PARA ATUALIZACAO DE
DADOS.TENTE MAIS TARDE(2)' em 15 das 17 linhas, nada foi gravado, e todas sairam
como 'Ok' na conferencia: a mensagem nao estava no mapa e o padrao era 'Ok'.
"""
import os

import pytest

MSG_Z03 = "Z03-SIAFI INDISPONIVEL PARA ATUALIZACAO DE DADOS.TENTE MAIS TARDE(2)"


@pytest.fixture
def traduzir_progresso(monkeypatch, tmp_path):
    # login.py monta os caminhos do OneDrive ao ser importado.
    monkeypatch.setenv('ONEDRIVE_BASE', os.getenv('ONEDRIVE_BASE') or str(tmp_path))
    from login import traduzir_progresso
    return traduzir_progresso


def test_registro_efetuado_vira_ok(traduzir_progresso):
    assert traduzir_progresso("0011-REGISTRO EFETUADO.") == 'Ok'
    assert traduzir_progresso("  0011-REGISTRO EFETUADO.  ") == 'Ok'


def test_siafi_indisponivel_tem_mensagem_propria(traduzir_progresso):
    assert (traduzir_progresso(MSG_Z03)
            == 'SIAFI indisponível para atualização, tente mais tarde')


def test_siafi_indisponivel_com_outro_codigo_entre_parenteses(traduzir_progresso):
    msg = MSG_Z03.replace('(2)', '(7)')
    assert (traduzir_progresso(msg)
            == 'SIAFI indisponível para atualização, tente mais tarde')


@pytest.mark.parametrize('retorno', [
    "X99-MENSAGEM QUE O ROBO NUNCA VIU",
    "",
    "   ",
    None,
])
def test_mensagem_desconhecida_vira_erro(traduzir_progresso, retorno):
    assert traduzir_progresso(retorno) == 'Erro'


@pytest.mark.parametrize('retorno, esperado', [
    ("0139- VALOR A APROVAR MAIOR QUE SALDO DISPONIVEL NO PROJ/ATIV.",
     'Valor a aprovar maior que o saldo disponível'),
    ("E90 - SALDO ZERADO NA CONTA 99902030400 NO MES: 14",
     'Saldo zerado na conta'),
    ("0017-TECLE PF5 PARA CONFIRMAR OU PF2 PARA ANULAR.",
     'Operação não confirmada no SIAFI'),
])
def test_erros_ja_mapeados_nao_mudam(traduzir_progresso, retorno, esperado):
    assert traduzir_progresso(retorno) == esperado
