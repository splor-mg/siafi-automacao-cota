import time

from telegram_mensagens import (agrupar_linhas, autorizado, formatar_duracao,
                                montar_final, montar_progresso, muito_antigo,
                                redigir)

GRUPO = '-1001234567890'


def update_de(chat_id, texto='/rodar', is_bot=False, quando=None):
    return {
        'update_id': 1,
        'message': {
            'message_id': 10,
            'date': int(quando if quando is not None else time.time()),
            'chat': {'id': chat_id},
            'from': {'id': 42, 'first_name': 'Guilherme', 'is_bot': is_bot},
            'text': texto,
        },
    }


def test_aceita_mensagem_do_grupo_autorizado():
    assert autorizado(update_de(int(GRUPO)), GRUPO) is True


def test_recusa_mensagem_de_outro_chat():
    assert autorizado(update_de(999), GRUPO) is False


def test_recusa_mensagem_de_bot():
    assert autorizado(update_de(int(GRUPO), is_bot=True), GRUPO) is False


def test_recusa_edicao_de_mensagem():
    """Edicao chega em 'edited_message'. Reprocessar edicao dispararia o robo
    de novo a partir de uma mensagem antiga."""
    up = update_de(int(GRUPO))
    up['edited_message'] = up.pop('message')
    assert autorizado(up, GRUPO) is False


def test_recusa_update_sem_mensagem():
    assert autorizado({'update_id': 1, 'callback_query': {}}, GRUPO) is False


def test_update_recente_nao_e_antigo():
    agora = time.time()
    assert muito_antigo(update_de(int(GRUPO), quando=agora), agora=agora) is False


def test_update_de_dez_minutos_atras_e_antigo():
    agora = time.time()
    up = update_de(int(GRUPO), quando=agora - 600)
    assert muito_antigo(up, agora=agora) is True


def test_redige_a_senha_do_texto():
    texto = 'falha ao logar com senha SEGREDO123 no SIAFI'
    assert redigir(texto, ['SEGREDO123']) == 'falha ao logar com senha *** no SIAFI'


def test_redigir_ignora_segredos_vazios():
    assert redigir('texto qualquer', ['', None]) == 'texto qualquer'


def eventos_de_exemplo():
    return [
        {'tipo': 'planilha', 'texto': '1 planilha(s) lida(s), validação OK (4 linhas)'},
        {'tipo': 'login', 'texto': 'Login no SIAFI realizado'},
        {'tipo': 'pendentes', 'texto': '4 linha(s) pendente(s): 2, 3, 4, 5',
         'linhas': [2, 3, 4, 5]},
        {'tipo': 'linha_pulada', 'texto': '...', 'linha': 2, 'motivo': 'IAG 1'},
        {'tipo': 'linha_pulada', 'texto': '...', 'linha': 3, 'motivo': 'IAG 1'},
        {'tipo': 'linha', 'texto': '...', 'linha': 4, 'operacao': 'aprovação',
         'uo': '1261', 'acao': '4511', 'fonte': '10', 'valor': 7400000},
        {'tipo': 'retorno', 'texto': '...', 'retorno': '0011-REGISTRO EFETUADO.'},
        {'tipo': 'resultado', 'texto': '...', 'linha': 4, 'ok': True, 'progresso': 'Ok'},
        {'tipo': 'linha', 'texto': '...', 'linha': 5, 'operacao': 'aprovação',
         'uo': '1261', 'acao': '2128', 'fonte': '10', 'valor': 50000000},
        {'tipo': 'retorno', 'texto': '...', 'retorno': '0011-REGISTRO EFETUADO.'},
        {'tipo': 'resultado', 'texto': '...', 'linha': 5, 'ok': True, 'progresso': 'Ok'},
        {'tipo': 'fim', 'texto': 'Fluxo finalizado'},
        {'tipo': 'planilha_final', 'texto': 'Planilha atualizada e movida ...',
         'arquivo': 'Conferencia arquivo robo 25.08.xlsx'},
    ]


def test_formatar_duracao():
    assert formatar_duracao(45) == '45s'
    assert formatar_duracao(192) == '3min12s'
    assert formatar_duracao(3720) == '1h02min'


def test_progresso_sai_vazio_antes_de_saber_as_pendentes():
    assert montar_progresso(eventos_de_exemplo()[:2]) is None


def test_progresso_junta_planilha_login_e_pendentes():
    msg = montar_progresso(eventos_de_exemplo())
    assert msg == ('1 planilha(s) lida(s), validação OK (4 linhas)\n'
                   'Login no SIAFI realizado\n'
                   '4 linha(s) pendente(s): 2, 3, 4, 5')


def test_agrupar_associa_retorno_a_ultima_linha_aberta():
    itens = agrupar_linhas(eventos_de_exemplo())
    assert [i['linha'] for i in itens] == [2, 3, 4, 5]
    assert itens[0]['pulada'] is True
    assert itens[2]['retorno'] == '0011-REGISTRO EFETUADO.'
    assert itens[2]['ok'] is True
    assert itens[3]['retorno'] == '0011-REGISTRO EFETUADO.'


def test_final_traz_cabecalho_linhas_e_resumo():
    msg = montar_final(eventos_de_exemplo(), codigo=0, duracao_seg=192)
    assert 'Robô SIAFI · concluído em 3min12s' in msg
    assert 'Linha 2 · pulada (IAG 1)' in msg
    assert ('Linha 4 · aprovação · UO 1261 · Ação 4511 · Fonte 10 · '
            'R$ 74.000,00') in msg
    assert 'R$ 500.000,00' in msg
    assert '0011-REGISTRO EFETUADO.' in msg
    assert '4 linhas · 2 efetuada(s) · 2 pulada(s) · 0 com erro' in msg
    assert 'Planilha: Conferencia arquivo robo 25.08.xlsx' in msg


def test_final_marca_falha_e_mostra_o_erro():
    eventos = eventos_de_exemplo()[:8] + [
        {'tipo': 'erro', 'texto': 'Execução interrompida por erro: TimeoutError: x'},
    ]
    msg = montar_final(eventos, codigo=1, duracao_seg=60)
    assert 'FALHOU (código 1)' in msg
    assert 'Execução interrompida por erro' in msg


def test_final_conta_linha_com_erro():
    eventos = eventos_de_exemplo()[:8]
    eventos[7] = {'tipo': 'resultado', 'texto': '...', 'linha': 4, 'ok': False,
                  'progresso': 'Saldo zerado na conta'}
    msg = montar_final(eventos, codigo=0, duracao_seg=10)
    assert '3 linhas · 0 efetuada(s) · 2 pulada(s) · 1 com erro' in msg


def test_final_escapa_html_do_retorno_do_siafi():
    eventos = eventos_de_exemplo()[:7]
    eventos[6] = {'tipo': 'retorno', 'texto': '...', 'retorno': 'ERRO <A & B>'}
    msg = montar_final(eventos, codigo=0, duracao_seg=10)
    assert '&lt;A &amp; B&gt;' in msg
    assert '<A & B>' not in msg


def test_final_poda_linhas_efetuadas_quando_estoura_o_limite():
    """Acima de 4096 caracteres o Telegram recusa a mensagem. As linhas com
    erro sao as que exigem acao, entao sao elas que sobrevivem a poda."""
    eventos = eventos_de_exemplo()[:3]
    for linha in range(10, 210):
        eventos += [
            {'tipo': 'linha', 'texto': '...', 'linha': linha,
             'operacao': 'aprovação', 'uo': '1261', 'acao': '4511',
             'fonte': '10', 'valor': 7400000},
            {'tipo': 'retorno', 'texto': '...', 'retorno': '0011-REGISTRO EFETUADO.'},
            {'tipo': 'resultado', 'texto': '...', 'linha': linha, 'ok': True,
             'progresso': 'Ok'},
        ]
    eventos += [
        {'tipo': 'linha', 'texto': '...', 'linha': 999, 'operacao': 'aprovação',
         'uo': '1261', 'acao': '4511', 'fonte': '10', 'valor': 7400000},
        {'tipo': 'retorno', 'texto': '...', 'retorno': 'E90 - SALDO ZERADO NA CONTA'},
        {'tipo': 'resultado', 'texto': '...', 'linha': 999, 'ok': False,
         'progresso': 'Saldo zerado na conta'},
    ]

    msg = montar_final(eventos, codigo=0, duracao_seg=600)

    assert len(msg) <= 4096
    assert 'Linha 999' in msg          # a que deu erro sobrevive
    assert 'linha(s) efetuada(s) (veja /log)' in msg
    assert '200 efetuada(s)' in msg    # o resumo continua contando tudo


def test_final_com_centenas_de_erros_continua_html_valido():
    """Cortar a string HTML pronta deixaria <pre> sem fechamento, e o Telegram
    recusaria a mensagem inteira — a equipe nao receberia nada."""
    eventos = eventos_de_exemplo()[:3]
    for linha in range(10, 310):
        eventos += [
            {'tipo': 'linha', 'texto': '...', 'linha': linha,
             'operacao': 'aprovação', 'uo': '1261', 'acao': '4511',
             'fonte': '10', 'valor': 7400000},
            {'tipo': 'retorno', 'texto': '...',
             'retorno': '0139- VALOR A APROVAR MAIOR QUE SALDO DISPONIVEL NO PROJ/ATIV.'},
            {'tipo': 'resultado', 'texto': '...', 'linha': linha, 'ok': False,
             'progresso': 'Valor a aprovar maior que o saldo disponível'},
        ]

    msg = montar_final(eventos, codigo=0, duracao_seg=600)

    assert len(msg) <= 4096
    assert msg.count('<pre>') == 1
    assert msg.count('</pre>') == 1
    assert msg.index('<pre>') < msg.index('</pre>')
    assert 'mensagem cortada' in msg


def test_final_escapa_nome_de_arquivo_com_caractere_especial():
    eventos = eventos_de_exemplo()
    eventos[-1] = {'tipo': 'planilha_final', 'texto': '...',
                   'arquivo': 'Remanejamento Fulano & Cia <2>.xlsx'}
    msg = montar_final(eventos, codigo=0, duracao_seg=10)
    assert 'Fulano &amp; Cia &lt;2&gt;.xlsx' in msg
    assert '<2>' not in msg


def test_final_escapa_texto_do_erro():
    eventos = eventos_de_exemplo()[:8] + [
        {'tipo': 'erro',
         'texto': 'Execução interrompida por erro: KeyError: <coluna & tal>'},
    ]
    msg = montar_final(eventos, codigo=1, duracao_seg=60)
    assert '&lt;coluna &amp; tal&gt;' in msg
    assert '<coluna' not in msg


def test_linha_sem_valor_mostra_o_motivo_e_nao_fala_em_interrupcao():
    """Linha sem valor nunca chega ao SIAFI, entao nunca ha 'retorno'. Dizer
    'execucao interrompida' contradiria o cabecalho 'concluido'."""
    eventos = eventos_de_exemplo()[:3] + [
        {'tipo': 'linha', 'texto': '...', 'linha': 6, 'operacao': 'sem valor',
         'uo': '1261', 'acao': '4511', 'fonte': '10', 'valor': 0},
        {'tipo': 'resultado', 'texto': '...', 'linha': 6, 'ok': False,
         'progresso': 'Linha sem valor de anulação/aprovação'},
    ]
    msg = montar_final(eventos, codigo=0, duracao_seg=5)
    assert 'Linha sem valor de anulação/aprovação' in msg
    assert 'execução interrompida' not in msg


def test_linha_sem_resultado_nenhum_admite_interrupcao():
    """Se o robo caiu depois de abrir a linha e antes de qualquer resultado, ai
    sim 'execucao interrompida' e a informacao correta."""
    eventos = eventos_de_exemplo()[:3] + [
        {'tipo': 'linha', 'texto': '...', 'linha': 7, 'operacao': 'aprovação',
         'uo': '1261', 'acao': '4511', 'fonte': '10', 'valor': 7400000},
        {'tipo': 'erro', 'texto': 'Execução interrompida por erro: TimeoutError'},
    ]
    msg = montar_final(eventos, codigo=1, duracao_seg=30)
    assert 'sem retorno (execução interrompida)' in msg
