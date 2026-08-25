import time

from telegram_mensagens import autorizado, muito_antigo, redigir

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
