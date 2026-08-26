"""A falha de validacao precisa chegar ao grupo, nao so ao log.

Quando a consolidacao reprova, o robo aborta antes de tocar no SIAFI — o que
esta certo. Mas quem acionou pelo Telegram precisa saber QUAL planilha corrigir
e o que nela esta errado, sem depender de alguem abrir o log no servidor.
"""
from consolida import resumir_erros


def test_resumo_traz_arquivo_coluna_e_motivo():
    erros = [('Decreto ação 4341.xlsx', None, 'UO Financiadora', None,
              'Colunas obrigatórias ausentes na planilha')]

    resumo = resumir_erros(erros)

    assert 'Decreto ação 4341.xlsx' in resumo
    assert 'UO Financiadora' in resumo
    assert 'Colunas obrigatórias ausentes na planilha' in resumo
    assert 'Nada foi consolidado' in resumo


def test_resumo_diz_a_linha_quando_o_erro_e_de_linha():
    erros = [('planilha.xlsx', 14, 'Fonte', 'abc', 'valor não numérico')]

    resumo = resumir_erros(erros)

    assert 'linha 14' in resumo
    assert 'Fonte' in resumo


def test_resumo_agrupa_por_arquivo():
    erros = [
        ('a.xlsx', 2, 'Fonte', '', 'valor inválido'),
        ('b.xlsx', 3, 'Grupo', '', 'valor inválido'),
        ('a.xlsx', 5, 'IAG', '', 'valor inválido'),
    ]

    resumo = resumir_erros(erros)

    assert resumo.count('a.xlsx') == 1
    assert resumo.count('b.xlsx') == 1


def test_resumo_limita_para_caber_na_mensagem_do_telegram():
    """Uma planilha muito errada geraria centenas de linhas; o grupo recebe o
    suficiente para agir e o resto fica no /log."""
    erros = [('arq.xlsx', i, 'Fonte', '', 'valor inválido') for i in range(30)]

    resumo = resumir_erros(erros, limite=5)

    assert 'e mais 25 problema(s)' in resumo
    assert len(resumo) < 1000
