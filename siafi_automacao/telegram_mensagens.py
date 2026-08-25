"""Montagem das mensagens do Telegram e regras de autorizacao.

Funcoes puras, sem rede e sem estado: o bot_telegram.py cuida do I/O. Assim
tudo que decide "quem pode acionar" e "o que sai no grupo" e testavel sem
tocar na API do Telegram nem no SIAFI.
"""

IDADE_MAXIMA_UPDATE = 300  # segundos


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
