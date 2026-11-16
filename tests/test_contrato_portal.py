"""O que o Portal Orçamentário (repositório pedidos-cota) espera deste robô.

O Portal não importa nada daqui: ele escreve a planilha em Remanejamentos e lê
a conferência de volta. O contrato é o formato dos dois arquivos, e do lado de
lá ele está copiado à mão (pedidos_cota/planilha.py e pedidos_cota/resultado.py).
Mudar um destes pontos aqui deixa todos os outros testes verdes e muda, em
silêncio, o que o órgão vê no Portal.

As colunas da conferência já estão amarradas em tests/test_coluna_pedido.py.
Aqui ficam a planilha de entrada e os textos da coluna Progresso.
"""
import os

import pytest
from openpyxl import Workbook

import consolida

# pedidos_cota/planilha.py: ABA_DA_ENTREGA e COLUNAS_ENTREGA, por extenso.
ABA_DO_PORTAL = 'Remanejamento Cota Orçamentaria'
COLUNAS_QUE_O_PORTAL_ESCREVE = [
    'UO_COD', 'Grupo', 'IAG', 'Fonte', 'IPU', 'Ação', 'GLOBAL', 'AMARRADO',
    'Anular', 'Aprovar', 'UO Financiadora',
]


@pytest.fixture
def login(monkeypatch, tmp_path):
    # login.py monta os caminhos do OneDrive ao ser importado.
    monkeypatch.setenv('ONEDRIVE_BASE', os.getenv('ONEDRIVE_BASE') or str(tmp_path))
    import login
    return login


def planilha_do_portal(caminho, linhas):
    """Escreve o arquivo do jeito que o pedidos_cota.planilha.gerar() escreve."""
    livro = Workbook()
    aba = livro.active
    aba.title = ABA_DO_PORTAL
    aba.append(COLUNAS_QUE_O_PORTAL_ESCREVE)
    for linha in linhas:
        aba.append(linha)
    livro.save(caminho)
    return str(caminho)


def test_planilha_escrita_pelo_portal_passa_na_validacao(tmp_path):
    """Global, amarrado com zero à esquerda (texto), amarrado acima de 999
    (número) e IPU 2 com UO financiadora: as formas que o Portal entrega."""
    arquivo = planilha_do_portal(tmp_path / '1501-2026-0031 SEPLAG.xlsx', [
        [1501, 3, 0, 10, 1, 4485, 'x', None, None, 1500.5, None],
        [1501, 3, 0, 10, 1, 4485, None, '0308', 250.0, None, None],
        [1501, 4, 1, 60, 2, 4365, None, 3390, None, 99.99, 1251],
    ])

    assert consolida.validar_todos([arquivo]) == []
    assert len(consolida.ler_arquivo_origem(arquivo)) == 3


def test_so_registro_efetuado_conta_como_executado_no_portal(login):
    """pedidos_cota/resultado.py: EXECUTOU = 'ok', comparado sem maiúsculas."""
    assert login.traduzir_progresso('0011-REGISTRO EFETUADO.').lower() == 'ok'


def test_resultados_incertos_tem_o_texto_que_o_portal_reconhece(login):
    """pedidos_cota/resultado.py: INCERTOS. Para estes dois o órgão não reenvia
    o pedido; a coordenação confere no SIAFI e corrige o resultado. Com outro
    texto o Portal trataria como falha comum, o órgão reenviaria e a cota
    poderia sair duas vezes."""
    incertos = ('erro', 'interrompida - verificar no siafi')

    assert login.traduzir_progresso('X99-MENSAGEM QUE O ROBO NUNCA VIU').lower() in incertos
    assert login.PROGRESSO_INCERTO.lower() in incertos
    assert login.PROGRESSO_INCERTO.lower() != 'erro'


def test_elemento_item_nao_marcado_tem_o_texto_que_o_portal_reconhece(login):
    """pedidos_cota/resultado.py: ELEMENTO_ITEM_NAO_MARCADO, a única falha que
    a DCMEFO decide (aprovação pelo módulo) antes de o órgão agir."""
    retorno = '0139- ELEMENTO/ITEM NAO MARCADO PARA UO BENEFICIADA.'

    assert (login.traduzir_progresso(retorno).lower()
            == 'elemento/item não marcado para a uo beneficiada')
