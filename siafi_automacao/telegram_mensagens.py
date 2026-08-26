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


def ler_lista_de_ids(valor):
    """Converte 'ID_A, ID_B' vindo do .env numa lista, tolerando espacos."""
    if not valor:
        return []
    return [pedaco.strip() for pedaco in valor.split(',') if pedaco.strip()]


def pode_rodar(update, usuarios_autorizados):
    """Quem, dentro do grupo, pode disparar o robo.

    Lista vazia mantem o comportamento anterior a esta trava: qualquer membro
    do grupo aciona. Com lista preenchida, so os ids nela — util quando o
    grupo tem gente que acompanha o resultado mas nao deve aprovar cota.

    Compara como texto porque o .env entrega string e o Telegram entrega int.
    """
    if not usuarios_autorizados:
        return True
    msg = update.get('message') or {}
    permitidos = {str(u) for u in usuarios_autorizados}
    return str(msg.get('from', {}).get('id')) in permitidos


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
            # .get em grupo/ipu: eventos gravados por versoes anteriores do
            # robo nao os tinham, e um KeyError aqui derrubaria a mensagem
            # final inteira.
            itens.append({'linha': ev['linha'], 'pulada': False,
                          'operacao': ev['operacao'], 'uo': ev['uo'],
                          'acao': ev['acao'], 'grupo': ev.get('grupo'),
                          'fonte': ev['fonte'], 'ipu': ev.get('ipu'),
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

    partes = [f"Linha {item['linha']}", item['operacao'],
              f"UO {item['uo']}", f"Ação {item['acao']}"]
    if item.get('grupo') is not None:
        partes.append(f"Grupo {item['grupo']}")
    partes.append(f"Fonte {item['fonte']}")
    if item.get('ipu') is not None:
        partes.append(f"IPU {item['ipu']}")
    partes.append(formatar_valor(item['valor']))
    cabecalho = ' · '.join(partes)

    if item['retorno']:
        detalhe = item['retorno']
    elif item.get('progresso'):
        # Linha que nunca chegou ao SIAFI (ex.: sem valor preenchido na
        # planilha). O 'progresso' diz o motivo real; dizer "execucao
        # interrompida" aqui seria mentira, a execucao terminou bem.
        detalhe = item['progresso']
    else:
        detalhe = 'sem retorno (execução interrompida)'

    return f"{cabecalho}\n   {detalhe}"


def _montar(cabecalho, corpo, rodape):
    return f"{cabecalho}\n\n<pre>{escape(corpo)}</pre>\n\n{rodape}"


def _cortar_corpo(cabecalho, corpo, rodape, limite):
    """Corta o corpo por linhas inteiras ate a mensagem montada caber.

    Cortar a string HTML ja pronta deixaria a tag <pre> sem fechamento ou uma
    entidade (&amp;) pela metade, e o Telegram recusa a mensagem inteira por
    HTML invalido — a equipe nao receberia nada.
    """
    aviso = '\n… (mensagem cortada, veja /log)'
    while corpo and len(_montar(cabecalho, corpo + aviso, rodape)) > limite:
        corpo = '\n'.join(corpo.split('\n')[:-1])
    return corpo + aviso


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
        rodape += f'\nPlanilha: {escape(planilha)}'

    # Todos os motivos, nao so o primeiro: a causa real (VPN fora, SIAFI no ar)
    # vem antes do aviso generico de interrupcao, e o grupo precisa dos dois
    # para saber se e problema de rede ou do robo.
    for erro in (e['texto'] for e in eventos if e['tipo'] == 'erro'):
        rodape += f'\n{escape(erro)}'

    # 'aviso' e o caso benigno (nada a processar): explica o resultado sem o
    # tom de falha, porque a execucao terminou bem.
    for aviso in (e['texto'] for e in eventos if e['tipo'] == 'aviso'):
        rodape += f'\n{escape(aviso)}'

    if not itens:
        # Um <pre> vazio vira um buraco branco no meio da mensagem.
        return f'{cabecalho}\n\nNenhuma linha chegou a ser processada.\n\n{rodape}'

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

    mensagem = _montar(cabecalho, corpo, rodape)
    if len(mensagem) <= limite:
        return mensagem

    # Guarda final: nem a poda bastou (execucao com centenas de erros).
    return _montar(cabecalho, _cortar_corpo(cabecalho, corpo, rodape, limite),
                   rodape)
