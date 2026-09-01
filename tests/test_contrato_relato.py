"""Amarra o robo ao bot: os campos que o robo emite sao os que o bot consome.

Sem este arquivo, renomear um campo num relato() do login.py deixa os outros
testes todos verdes e quebra a mensagem do Telegram so em producao — que e
justamente onde ninguem quer descobrir.
"""
import ast
import os

import pytest

from telegram_mensagens import montar_final, montar_progresso

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTES = ('login.py', 'consolida.py', 'fluxo_aprovar.py', 'fluxo_anular.py')

# O que o bot precisa receber de cada tipo de evento. Mexeu aqui, mexa tambem
# em telegram_mensagens.agrupar_linhas()/montar_final() — e vice-versa.
CONTRATO = {
    'planilha':       set(),
    'login':          set(),
    'pendentes':      {'linhas'},
    'linha_pulada':   {'linha', 'motivo'},
    'linha':          {'linha', 'operacao', 'uo', 'acao', 'grupo', 'fonte',
                       'ipu', 'valor'},
    'retorno':        {'retorno'},
    'resultado':      {'linha', 'ok', 'progresso'},
    'fim':            set(),
    'planilha_final': {'arquivo'},
    'erro':           set(),
    'aviso':          set(),
}

# O robo de credito vive em outro repositorio e reporta por documento, nao por
# linha de planilha. O bot le os dois com o mesmo montar_final.
REPO_CREDITO = os.path.expanduser('~/code/splor-mg/siafi-automacao-credito')
FONTES_CREDITO = ('login.py', 'consolida.py', 'resultado.py')

CONTRATO_CREDITO = {
    'planilha':       set(),
    'planilha_final': {'arquivo'},
    'login':     set(),
    'pendentes': set(),
    'documento': {'linha', 'uo', 'nr_doc', 'ok'},
    'fim':       set(),
    'erro':      set(),
    'aviso':     set(),
}


def campos_emitidos(raiz=RAIZ, fontes=FONTES):
    """Le o codigo-fonte do robo e extrai os campos de cada chamada a relato().

    Usa AST em vez de executar o robo: rodar o login.py de verdade exigiria o
    SIAFI, o OneDrive e credenciais.
    """
    emitidos = {}
    for nome in fontes:
        with open(os.path.join(raiz, 'siafi_automacao', nome), encoding='utf-8') as f:
            arvore = ast.parse(f.read())

        for no in ast.walk(arvore):
            if not (isinstance(no, ast.Call)
                    and isinstance(no.func, ast.Name)
                    and no.func.id == 'relato'
                    and no.args
                    and isinstance(no.args[0], ast.Constant)):
                continue
            tipo = no.args[0].value
            emitidos.setdefault(tipo, set()).update(kw.arg for kw in no.keywords)
    return emitidos


def test_o_robo_emite_exatamente_os_campos_que_o_bot_consome():
    assert campos_emitidos() == CONTRATO


def test_todo_tipo_emitido_tem_tratamento_no_bot():
    """Um tipo novo que o bot nao conhece sumiria da mensagem em silencio."""
    assert set(campos_emitidos()) == set(CONTRATO)


def eventos_da_execucao_real():
    """Reproduz a execucao de 25/08/2026 12:19 (data/logs/robo-20260825-121943.log).

    Dados reais de producao, e nao fixture inventada: se a montagem da mensagem
    quebrar para uma execucao que ja aconteceu de verdade, o teste avisa.
    """
    linhas = [
        (23, '4510', 887800000,  '0011-REGISTRO EFETUADO.', 'Ok'),
        (24, '2128', 600000000,  '0011-REGISTRO EFETUADO.', 'Ok'),
        (25, '2128', 1467555900, '0011-REGISTRO EFETUADO.', 'Ok'),
        (26, '2126', 675000000,
         '0139- PROGRAMA DE TRABALHO NAO ENCONTRADO PARA GM/FP.',
         'Programa de trabalho não encontrado para GM/FP'),
        (27, '4512', 1000000000, '0011-REGISTRO EFETUADO.', 'Ok'),
        (28, '4511', 6337680000,
         '0139- VALOR A APROVAR MAIOR QUE SALDO DISPONIVEL NO PROJ/ATIV.',
         'Valor a aprovar maior que o saldo disponível'),
        (29, '2095', 100000000,  '0011-REGISTRO EFETUADO.', 'Ok'),
        (30, '2064', 262603300,  '0011-REGISTRO EFETUADO.', 'Ok'),
        (31, '4527', 850000000,  '0011-REGISTRO EFETUADO.', 'Ok'),
    ]

    eventos = [
        {'tipo': 'planilha', 'texto': '1 planilha(s) lida(s), validação OK (33 linhas)'},
        {'tipo': 'login', 'texto': 'Login no SIAFI realizado'},
        {'tipo': 'pendentes', 'texto': '12 linha(s) pendente(s): 23, 24, 25, 26, '
                                       '27, 28, 29, 30, 31, 32, 33, 34',
         'linhas': list(range(23, 35))},
    ]
    for linha, acao, valor, retorno, progresso in linhas:
        eventos += [
            {'tipo': 'linha', 'texto': '...', 'linha': linha,
             'operacao': 'aprovação', 'uo': '1261', 'acao': acao,
             'fonte': '10', 'valor': valor},
            {'tipo': 'retorno', 'texto': '...', 'retorno': retorno},
            {'tipo': 'resultado', 'texto': '...', 'linha': linha,
             'ok': progresso == 'Ok', 'progresso': progresso},
        ]
    for linha in (32, 33, 34):
        eventos.append({'tipo': 'linha_pulada', 'texto': '...', 'linha': linha,
                        'motivo': 'IAG 1'})

    eventos += [
        {'tipo': 'fim', 'texto': 'Fluxo finalizado'},
        {'tipo': 'planilha_final', 'texto': 'Planilha atualizada e movida ...',
         'arquivo': 'Conferencia arquivo robo 25.08.xlsx'},
    ]
    return eventos


def test_execucao_real_vira_mensagem_com_a_contagem_certa():
    """O log de 25/08 registra 7 efetuadas, 2 com erro e 3 puladas."""
    msg = montar_final(eventos_da_execucao_real(), codigo=0, duracao_seg=372)

    assert '12 linhas · 7 efetuada(s) · 3 pulada(s) · 2 com erro' in msg
    assert len(msg) <= 4096
    assert msg.count('<pre>') == 1 and msg.count('</pre>') == 1


def test_execucao_real_mostra_valores_em_reais():
    """887800000 na planilha e R$ 8.878.000,00 — errar a escala aqui faria a
    equipe aprovar cota acreditando num valor 100x menor ou maior."""
    msg = montar_final(eventos_da_execucao_real(), codigo=0, duracao_seg=372)

    assert 'R$ 8.878.000,00' in msg      # linha 23
    assert 'R$ 14.675.559,00' in msg     # linha 25
    assert 'R$ 63.376.800,00' in msg     # linha 28


def test_execucao_real_gera_a_mensagem_de_progresso():
    msg = montar_progresso(eventos_da_execucao_real())

    assert msg.startswith('1 planilha(s) lida(s)')
    assert 'Login no SIAFI realizado' in msg
    assert '12 linha(s) pendente(s)' in msg


@pytest.mark.skipif(not os.path.isdir(REPO_CREDITO),
                    reason='repositorio do robo de credito nao esta nesta maquina')
def test_o_robo_de_credito_emite_o_que_o_bot_consome():
    """Mesma amarra do robo de cota, para o outro repositorio.

    Sem isto, renomear um campo no resultado.py do credito deixaria a suite
    verde e a mensagem do /credito quebraria so em producao.
    """
    assert campos_emitidos(REPO_CREDITO, FONTES_CREDITO) == CONTRATO_CREDITO


@pytest.mark.skipif(not os.path.isdir(REPO_CREDITO),
                    reason='repositorio do robo de credito nao esta nesta maquina')
def test_todo_tipo_do_credito_tem_tratamento_no_bot():
    """Um tipo que o bot nao conhece sumiria da mensagem em silencio."""
    conhecidos = set(CONTRATO) | {'documento'}
    assert set(campos_emitidos(REPO_CREDITO, FONTES_CREDITO)) <= conhecidos
