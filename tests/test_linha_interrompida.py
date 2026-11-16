"""Aviso da linha que parou no meio.

Em 16/10/2026 (duas vezes) e 05/11/2026 a execucao morreu com 'Keyboard
locked' na linha 36, sempre com IPU 2. 'Keyboard locked' e o sintoma: o robo
digitou numa posicao protegida porque o SIAFI nao foi para a tela esperada. A
mensagem do SIAFI que explica o motivo estava na tela e nunca foi lida — o
grupo so soube que "nao da para saber se a operacao entrou".
"""
import os

import pytest


@pytest.fixture
def aviso_linha_incerta(monkeypatch, tmp_path):
    # login.py monta os caminhos do OneDrive ao ser importado.
    monkeypatch.setenv('ONEDRIVE_BASE', os.getenv('ONEDRIVE_BASE') or str(tmp_path))
    from login import aviso_linha_incerta
    return aviso_linha_incerta


def test_aviso_diz_a_linha_e_que_ela_nao_sera_reprocessada(aviso_linha_incerta):
    aviso = aviso_linha_incerta(36, [])

    assert 'a linha 36 parou no meio' in aviso
    assert 'NÃO será reprocessada' in aviso


def test_aviso_leva_ao_grupo_a_mensagem_que_estava_na_tela(aviso_linha_incerta):
    tela = ['  0139- UO FINANCIADORA INVALIDA PARA A FONTE  ', '', 'SIAFI']

    aviso = aviso_linha_incerta(36, tela)

    assert 'Na tela do SIAFI estava: 0139- UO FINANCIADORA INVALIDA PARA A FONTE' in aviso


@pytest.mark.parametrize('tela', [[], ['   ', 'SIAFI']])
def test_sem_mensagem_na_tela_o_aviso_nao_inventa_uma(aviso_linha_incerta, tela):
    """Tela ilegivel (emulador morto) ou linha 1 em branco."""
    assert 'Na tela do SIAFI' not in aviso_linha_incerta(36, tela)
