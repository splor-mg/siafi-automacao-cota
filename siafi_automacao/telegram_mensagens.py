"""Montagem das mensagens do Telegram e regras de autorizacao.

Funcoes puras, sem rede e sem estado: o bot_telegram.py cuida do I/O. Assim
tudo que decide "quem pode acionar" e "o que sai no grupo" e testavel sem
tocar na API do Telegram nem no SIAFI.
"""

from html import escape

from relato import formatar_valor

IDADE_MAXIMA_UPDATE = 300  # segundos
LIMITE_TELEGRAM = 4096


def autorizado(update, chat_autorizado):
    """So aceita mensagem nova, de humano, vinda do grupo autorizado.

    Edicoes de mensagem chegam sob a chave 'edited_message' e por isso ja caem
    fora: reprocessar uma edicao dispararia o robo a partir de um comando
    antigo.
    """
    msg = update.get('message')
    if not msg:
        return False
    if msg.get('from', {}).get('is_bot'):
        return False
    return bool(str(msg.get('chat', {}).get('id')) == str(chat_autorizado))


def muito_antigo(update, agora, idade_maxima=IDADE_MAXIMA_UPDATE):
    """Comando velho demais para ser obedecido.

    Protege o caso de o bot ficar fora do ar e voltar com backlog: ninguem quer
    que o robo dispare sozinho por causa de um /rodar de uma hora atras.
    """
    msg = update.get('message') or {}
    return bool((agora - msg.get('date', 0)) > idade_maxima)


def redigir(texto, segredos):
    """Troca ocorrencias dos segredos por *** antes de qualquer coisa sair."""
    for segredo in segredos:
        if segredo:
            texto = texto.replace(segredo, '***')
    return texto


def formatar_duracao(segundos):
    segundos = int(segundos)
    if segundos < 60:
        return f'{segundos}s'
    minutos, s = divmod(segundos, 60)
    if minutos < 60:
        return f'{minutos}min{s:02d}s'
    horas, m = divmod(minutos, 60)
    return f'{horas}h{m:02d}min'


def montar_progresso(eventos):
    """Mensagem do marco intermediario.

    Devolve None enquanto o robo ainda nao souber quantas linhas vai processar
    — o bot fica tentando ate essa hora chegar.
    """
    pendentes = next((e for e in eventos if e['tipo'] == 'pendentes'), None)
    if not pendentes:
        return None

    partes = [e['texto'] for e in eventos if e['tipo'] in ('planilha', 'login')]
    partes.append(pendentes['texto'])
    return '\n'.join(partes)


def agrupar_linhas(eventos):
    """Junta cada linha com o retorno do SIAFI e o resultado que vieram depois.

    fluxo_aprovar/fluxo_anular nao conhecem o numero da linha, e nao precisam:
    o processamento e sequencial, entao o retorno pertence sempre a ultima
    linha aberta.
    """
    itens = []
    for ev in eventos:
        tipo = ev['tipo']
        if tipo == 'linha_pulada':
            itens.append({'linha': ev['linha'], 'pulada': True,
                          'motivo': ev['motivo'], 'ok': True, 'retorno': None})
        elif tipo == 'linha':
            itens.append({'linha': ev['linha'], 'pulada': False,
                          'operacao': ev['operacao'], 'uo': ev['uo'],
                          'acao': ev['acao'], 'fonte': ev['fonte'],
                          'valor': ev['valor'], 'retorno': None, 'ok': False})
        elif tipo == 'retorno' and itens and not itens[-1]['pulada']:
            itens[-1]['retorno'] = ev['retorno']
        elif tipo == 'resultado':
            for item in itens:
                if item['linha'] == ev['linha'] and not item['pulada']:
                    item['ok'] = ev['ok']
                    item['progresso'] = ev['progresso']
    return itens


def _texto_item(item):
    if item['pulada']:
        return f"Linha {item['linha']} · pulada ({item['motivo']})"

    cabecalho = (f"Linha {item['linha']} · {item['operacao']} · "
                 f"UO {item['uo']} · Ação {item['acao']} · "
                 f"Fonte {item['fonte']} · {formatar_valor(item['valor'])}")
    retorno = item['retorno'] or 'sem retorno (execução interrompida)'
    return f"{cabecalho}\n   {retorno}"


def _montar(cabecalho, corpo, rodape):
    return f"{cabecalho}\n\n<pre>{escape(corpo)}</pre>\n\n{rodape}"


def montar_final(eventos, codigo, duracao_seg, limite=LIMITE_TELEGRAM):
    itens = agrupar_linhas(eventos)
    duracao = formatar_duracao(duracao_seg)

    if codigo == 0:
        cabecalho = f'Robô SIAFI · concluído em {duracao}'
    else:
        cabecalho = f'Robô SIAFI · FALHOU (código {codigo}) após {duracao}'

    efetuadas = sum(1 for i in itens if not i['pulada'] and i['ok'])
    puladas = sum(1 for i in itens if i['pulada'])
    com_erro = sum(1 for i in itens if not i['pulada'] and not i['ok'])

    rodape = (f'{len(itens)} linhas · {efetuadas} efetuada(s) · '
              f'{puladas} pulada(s) · {com_erro} com erro')

    # So o nome do arquivo vai para o grupo; o 'texto' do evento carrega o
    # caminho completo do OneDrive, que interessa apenas ao log.
    planilha = next((e['arquivo'] for e in eventos
                     if e['tipo'] == 'planilha_final'), None)
    if planilha:
        rodape += f'\nPlanilha: {planilha}'

    erro = next((e['texto'] for e in eventos if e['tipo'] == 'erro'), None)
    if erro:
        rodape += f'\n{erro}'

    corpo = '\n'.join(_texto_item(i) for i in itens)
    mensagem = _montar(cabecalho, corpo, rodape)
    if len(mensagem) <= limite:
        return mensagem

    # Nao coube: as linhas com erro sao as que exigem acao de alguem, entao sao
    # elas que ficam. O resto vira uma contagem, e o log completo tem tudo.
    mantidos = [i for i in itens if i['pulada'] or not i['ok']]
    omitidas = len(itens) - len(mantidos)
    corpo = '\n'.join(_texto_item(i) for i in mantidos)
    corpo += f'\n…+{omitidas} linha(s) efetuada(s) (veja /log)'

    # Guarda final: se nem assim couber (execucao com centenas de erros), corta.
    return _montar(cabecalho, corpo, rodape)[:limite]
