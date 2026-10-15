"""PF5 que nao confirma a operacao.

Em 15/10/2026 a linha 24 (UO 1501, acao 4485, R$ 5.931,78) saiu como 'Ok' na
conferencia, mas o SIAFI tinha aberto a janela 'Inconsistencia no Registro da
Contabilizacao' (SIGG Z05 - SALDO INSUFICIENTE A CREDITAR) e nada foi gravado.
A linha 1 continuava em '0017-TECLE PF5 PARA CONFIRMAR...', mensagem que nao
estava no mapa de erros e por isso virava 'Ok'.
"""
import os

import pytest

import fluxo_anular
import fluxo_aprovar

MSG_0017 = "0017-TECLE PF5 PARA CONFIRMAR OU PF2 PARA ANULAR."
TITULO_JANELA = "Inconsistencia no Registro da Contabilizacao"


class EmuladorFalso:
    """Devolve a linha 1 final so depois dos dois PF5, como o SIAFI."""

    def __init__(self, linha1_final, linha4=''):
        self.linha1_final = linha1_final
        self.linha4 = linha4
        self.pf5 = 0
        self.leituras = []

    def string_get(self, ypos, xpos, length):
        self.leituras.append((ypos, xpos, length))
        if ypos == 1:
            return self.linha1_final if self.pf5 >= 2 else "0000-TELA INTERMEDIARIA"
        if (ypos, xpos) == (4, 19):
            return self.linha4.ljust(length)
        return ' ' * length

    def send_pf(self, n):
        if n == 5:
            self.pf5 += 1

    def fill_field(self, *args):
        pass

    def send_enter(self):
        pass

    def wait_for_field(self):
        pass

    def exec_command(self, cmd):
        pass


LINHA = {
    'tipo_global': 'x', 'tipo_amarrado': '0', 'month': '10', 'fonte': '60',
    'procedencia': '1', 'uo': '1501', 'grupo': '3', 'iag': '2',
    'acao': '4485', 'valor': '5931,78',
}


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr(fluxo_aprovar.time, 'sleep', lambda s: None)


@pytest.fixture
def traduzir_progresso(monkeypatch, tmp_path):
    # login.py monta os caminhos do OneDrive ao ser importado.
    monkeypatch.setenv('ONEDRIVE_BASE', os.getenv('ONEDRIVE_BASE') or str(tmp_path))
    from login import traduzir_progresso
    return traduzir_progresso


@pytest.mark.parametrize('fluxo', [fluxo_aprovar.aprovar, fluxo_anular.anular])
def test_janela_de_inconsistencia_vira_erro_de_saldo_contabil(fluxo, traduzir_progresso):
    em = EmuladorFalso(MSG_0017, linha4=TITULO_JANELA)

    retorno = fluxo(em, LINHA)

    assert retorno == TITULO_JANELA
    assert traduzir_progresso(retorno) == 'Erro de Saldo Contábil'


@pytest.mark.parametrize('fluxo', [fluxo_aprovar.aprovar, fluxo_anular.anular])
def test_0017_sem_janela_conhecida_nao_vira_ok(fluxo, traduzir_progresso):
    """Se o 0017 continua na tela, nada foi gravado, seja qual for o motivo."""
    em = EmuladorFalso(MSG_0017, linha4='')

    retorno = fluxo(em, LINHA)

    assert retorno == MSG_0017
    assert traduzir_progresso(retorno) == 'Operação não confirmada no SIAFI'


@pytest.mark.parametrize('fluxo', [fluxo_aprovar.aprovar, fluxo_anular.anular])
def test_registro_efetuado_continua_ok(fluxo, traduzir_progresso):
    em = EmuladorFalso("0011-REGISTRO EFETUADO.")

    retorno = fluxo(em, LINHA)

    assert retorno == "0011-REGISTRO EFETUADO."
    assert traduzir_progresso(retorno) == 'Ok'
    assert (4, 19, 46) not in em.leituras


@pytest.mark.parametrize('fluxo', [fluxo_aprovar.aprovar, fluxo_anular.anular])
def test_linha1_vazia_nao_le_a_janela(fluxo):
    """Com `in ("...")` sem virgula, '' casava como substring da 0017."""
    em = EmuladorFalso("", linha4=TITULO_JANELA)

    assert fluxo(em, LINHA) == ""
    assert (4, 19, 46) not in em.leituras
