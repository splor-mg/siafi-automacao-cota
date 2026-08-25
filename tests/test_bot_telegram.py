import time

import pytest

from bot_telegram import gravar_offset, ler_eventos, ler_offset


@pytest.fixture(autouse=True)
def estado_limpo():
    """EXECUCAO e global do modulo: sem isto um teste contamina o seguinte."""
    import bot_telegram
    bot_telegram.EXECUCAO.update(rodando=False, inicio=None, quem=None)
    yield
    bot_telegram.EXECUCAO.update(rodando=False, inicio=None, quem=None)


def test_offset_ausente_devolve_none(tmp_path):
    assert ler_offset(tmp_path / 'nao-existe') is None


def test_offset_grava_e_le(tmp_path):
    arquivo = tmp_path / '.telegram_offset'
    gravar_offset(105, arquivo)
    assert ler_offset(arquivo) == 105


def test_offset_corrompido_devolve_none(tmp_path):
    """Arquivo truncado por queda de energia nao pode derrubar o bot."""
    arquivo = tmp_path / '.telegram_offset'
    arquivo.write_text('lixo')
    assert ler_offset(arquivo) is None


def test_ler_eventos_ignora_linha_incompleta(tmp_path):
    """O bot le o .jsonl enquanto o robo ainda escreve nele: a ultima linha
    pode estar pela metade."""
    arquivo = tmp_path / 'relato.jsonl'
    arquivo.write_text('{"tipo": "login", "texto": "ok"}\n{"tipo": "lin',
                       encoding='utf-8')
    eventos = ler_eventos(arquivo)
    assert len(eventos) == 1
    assert eventos[0]['tipo'] == 'login'


def test_ler_eventos_de_arquivo_inexistente(tmp_path):
    assert ler_eventos(tmp_path / 'nao-existe') == []


def test_tratar_ignora_comando_desconhecido(monkeypatch):
    """Texto que nao e comando nao pode disparar nada."""
    import bot_telegram
    enviadas = []
    monkeypatch.setattr(bot_telegram, 'enviar', enviadas.append)
    monkeypatch.setattr(bot_telegram, 'comando_rodar',
                        lambda quem: enviadas.append('RODOU'))

    bot_telegram.tratar({'message': {'text': 'bom dia pessoal',
                                     'from': {'first_name': 'Ana'}}})

    assert enviadas == []


def test_tratar_aceita_comando_com_nome_do_bot(monkeypatch):
    """Em grupo o Telegram entrega '/rodar@nome_do_bot'."""
    import bot_telegram
    chamadas = []
    monkeypatch.setattr(bot_telegram, 'comando_rodar', chamadas.append)

    bot_telegram.tratar({'message': {'text': '/rodar@robo_siafi_bot',
                                     'from': {'first_name': 'Ana'}}})

    assert chamadas == ['Ana']


def test_caminhos_ultima_execucao_sem_arquivo(monkeypatch, tmp_path):
    import bot_telegram
    monkeypatch.setattr(bot_telegram, 'ARQUIVO_ULTIMA',
                        str(tmp_path / 'nao-existe'))
    assert bot_telegram.caminhos_ultima_execucao() == (None, None)


def test_caminhos_ultima_execucao_le_as_duas_linhas(monkeypatch, tmp_path):
    import bot_telegram
    arquivo = tmp_path / '.ultima_execucao'
    arquivo.write_text('/tmp/robo.log\n/tmp/relato.jsonl\n', encoding='utf-8')
    monkeypatch.setattr(bot_telegram, 'ARQUIVO_ULTIMA', str(arquivo))

    assert bot_telegram.caminhos_ultima_execucao() == (
        '/tmp/robo.log', '/tmp/relato.jsonl')


def test_executar_libera_o_estado_mesmo_se_o_processo_nao_subir(monkeypatch):
    """Sem o try/finally, uma falha ao iniciar o rodar.sh deixaria o estado
    preso em rodando=True e todo /rodar futuro seria recusado, sem ninguem no
    grupo entender por que."""
    import bot_telegram
    enviadas = []
    monkeypatch.setattr(bot_telegram, 'enviar', enviadas.append)

    def popen_quebrado(*args, **kwargs):
        raise OSError('bash nao encontrado')

    monkeypatch.setattr(bot_telegram.subprocess, 'Popen', popen_quebrado)
    bot_telegram.EXECUCAO.update(rodando=True, inicio=time.time(), quem='Ana')

    bot_telegram.executar('Ana')

    assert bot_telegram.EXECUCAO['rodando'] is False
    assert any('Falha ao executar' in m for m in enviadas)


def test_comando_rodar_recusa_quando_ja_ha_execucao(monkeypatch):
    """Duas execucoes simultaneas no SIAFI seriam um desastre."""
    import bot_telegram
    enviadas = []
    threads_iniciadas = []
    monkeypatch.setattr(bot_telegram, 'enviar', enviadas.append)
    monkeypatch.setattr(bot_telegram.threading, 'Thread',
                        lambda *a, **kw: threads_iniciadas.append(kw))

    bot_telegram.EXECUCAO.update(rodando=True, inicio=time.time(), quem='Ana')
    bot_telegram.comando_rodar('Bruno')

    assert threads_iniciadas == []
    assert any('Já tem execução em andamento' in m for m in enviadas)
