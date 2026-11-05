"""Coluna Pedido do conferência: o arquivo de origem de cada linha.

A ordenacao por UO mistura as linhas dos arquivos da rodada, e ate aqui so o
log dizia de qual arquivo cada uma tinha vindo.

O Portal Orcamentario tambem le essa planilha: monta um mapa com os nomes da
linha 1 da primeira aba e recusa o arquivo inteiro se faltar uma das
COLUNAS_DO_PORTAL. Por isso os testes de layout abaixo.
"""
import os
import shutil
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest
from openpyxl import load_workbook

import consolida

COLUNAS_DO_PORTAL = [
    'UO_COD', 'Grupo', 'IAG', 'Fonte', 'IPU', 'Ação', 'AMARRADO', 'Anular',
    'Aprovar', 'UO Financiadora', 'Progresso',
]


@pytest.fixture
def pastas(monkeypatch, tmp_path):
    p = SimpleNamespace(
        remanejamentos=tmp_path / 'Remanejamentos',
        segov=tmp_path / 'Remanejamentos (SEGOV)',
        conferencia=tmp_path / 'Conferencia arquivo robo',
        realizados=tmp_path / 'Realizados',
        saida=tmp_path / 'Robo (IPU 2)' / 'Python',
    )
    for pasta in vars(p).values():
        pasta.mkdir(parents=True)

    # O main() usa estas constantes, que vem do .env: sem trocar todas, o teste
    # moveria arquivos do OneDrive de verdade.
    monkeypatch.setattr(consolida, 'CONFERENCIA', str(p.conferencia))
    monkeypatch.setattr(consolida, 'REALIZADOS', str(p.realizados))
    monkeypatch.setattr(consolida, 'REALIZADOS_CONFERENCIA',
                        str(p.realizados / 'Conferencia Robo Realizados'))
    monkeypatch.setattr(consolida, 'ROBO_IPU2_PYTHON', str(p.saida))
    monkeypatch.setattr(consolida, 'PASTAS_REMANEJAMENTOS',
                        [str(p.remanejamentos), str(p.segov)])
    monkeypatch.setattr(consolida, 'relato', lambda *a, **k: None)
    return p


def escrever_origem(caminho, uo, acao, extra=None):
    linha = [uo, 3, 0, 10, 1, acao, 'x', None, None, 100.0, None]
    df = pd.DataFrame([linha], columns=consolida.COLUNAS_OBRIGATORIAS)
    for coluna, valor in (extra or {}).items():
        df[coluna] = valor
    df.to_excel(caminho, index=False)


def conferencia_de_hoje(pastas):
    hoje = date.today()
    return pastas.saida / f'Conferencia arquivo robo {hoje.day:02d}.{hoje.month:02d}.xlsx'


def ler_conferencia(pastas):
    return pd.read_excel(conferencia_de_hoje(pastas), dtype={'Pedido': str})


def cabecalho(caminho):
    ws = load_workbook(caminho).worksheets[0]
    return [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]


def devolver_para_a_conferencia(pastas):
    """O que o login.py faz ao terminar a rodada: o proximo consolida le daqui."""
    shutil.move(conferencia_de_hoje(pastas), pastas.conferencia)


def test_cada_linha_recebe_o_nome_do_proprio_arquivo(pastas):
    escrever_origem(pastas.remanejamentos / '2311-2026-0017 UNIMONTES.xlsx', 2311, 4001)
    escrever_origem(pastas.segov / '1501-2026-0031 SEPLAG.xlsx', 1501, 4485)

    consolida.main()

    df = ler_conferencia(pastas)
    assert dict(zip(df['UO_COD'], df['Pedido'])) == {
        2311: '2311-2026-0017 UNIMONTES',
        1501: '1501-2026-0031 SEPLAG',
    }


def test_nome_com_pontos_perde_so_a_extensao(pastas):
    escrever_origem(pastas.remanejamentos / 'Remanejamento 06.10.2026.1.xlsx', 2311, 4001)

    consolida.main()

    assert ler_conferencia(pastas)['Pedido'].tolist() == ['Remanejamento 06.10.2026.1']


def test_pedido_da_planilha_de_origem_nao_vale(pastas):
    escrever_origem(pastas.remanejamentos / '2311-2026-0017 UNIMONTES.xlsx', 2311, 4001,
                    extra={'Pedido': 'OUTRO PEDIDO'})

    consolida.main()

    assert ler_conferencia(pastas)['Pedido'].tolist() == ['2311-2026-0017 UNIMONTES']
    assert cabecalho(conferencia_de_hoje(pastas)).count('Pedido') == 1


def test_coluna_pedido_fica_entre_execucao_e_uo_cod(pastas):
    escrever_origem(pastas.remanejamentos / '2311-2026-0017 UNIMONTES.xlsx', 2311, 4001)

    consolida.main()

    assert cabecalho(conferencia_de_hoje(pastas))[:3] == ['Execução', 'Pedido', 'UO_COD']


def test_layout_continua_o_que_o_portal_le(pastas, monkeypatch, tmp_path):
    # login.py monta os caminhos do OneDrive ao ser importado.
    monkeypatch.setenv('ONEDRIVE_BASE', os.getenv('ONEDRIVE_BASE') or str(tmp_path))
    from login import formatar_planilha

    escrever_origem(pastas.remanejamentos / '2311-2026-0017 UNIMONTES.xlsx', 2311, 4001)
    consolida.main()

    # Vale tambem para a planilha formatada, que e a que fica na conferencia.
    arquivo = conferencia_de_hoje(pastas)
    wb = load_workbook(arquivo)
    formatar_planilha(wb.worksheets[0])
    wb.save(arquivo)

    nomes = cabecalho(arquivo)
    assert set(COLUNAS_DO_PORTAL) <= set(nomes)
    assert len(nomes) == len(set(nomes))


def test_segunda_rodada_do_dia_mantem_os_pedidos(pastas):
    escrever_origem(pastas.remanejamentos / '2311-2026-0017 UNIMONTES.xlsx', 2311, 4001)
    consolida.main()
    devolver_para_a_conferencia(pastas)

    escrever_origem(pastas.remanejamentos / '1501-2026-0031 SEPLAG.xlsx', 1501, 4485)
    consolida.main()

    df = ler_conferencia(pastas)
    assert df['Execução'].tolist() == [1, 2]
    assert df['Pedido'].tolist() == ['2311-2026-0017 UNIMONTES', '1501-2026-0031 SEPLAG']


def test_conferencia_de_antes_da_coluna_recebe_rodada_nova(pastas):
    """Dia da virada: o arquivo do dia ainda nao tem Pedido."""
    colunas = [c for c in consolida.COLUNAS_CONFERENCIA if c != 'Pedido']
    antigo = pd.DataFrame([[1, 2311, 3, 0, 10, 1, 4001, 'x', None, 100.0, None, None, 'Ok']],
                          columns=colunas)
    antigo.to_excel(pastas.conferencia / conferencia_de_hoje(pastas).name, index=False)

    escrever_origem(pastas.remanejamentos / '1501-2026-0031 SEPLAG.xlsx', 1501, 4485)
    consolida.main()

    df = ler_conferencia(pastas)
    assert df['Pedido'].isna().tolist() == [True, False]
    assert df['Pedido'].iloc[1] == '1501-2026-0031 SEPLAG'
    assert df['Progresso'].iloc[0] == 'Ok'


def test_nome_so_de_digitos_nao_perde_o_zero_na_segunda_rodada(pastas):
    escrever_origem(pastas.remanejamentos / '0123.xlsx', 2311, 4001)
    consolida.main()
    devolver_para_a_conferencia(pastas)

    escrever_origem(pastas.remanejamentos / '0456.xlsx', 1501, 4485)
    consolida.main()

    ws = load_workbook(conferencia_de_hoje(pastas)).worksheets[0]
    assert [ws.cell(row=r, column=2).value for r in (2, 3)] == ['0123', '0456']
