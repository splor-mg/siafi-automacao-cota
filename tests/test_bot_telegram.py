import os
import time

import pytest

from bot_telegram import gravar_offset, ler_eventos, ler_offset


@pytest.fixture(autouse=True)
def estado_limpo():
    """EXECUCAO e global do modulo: sem isto um teste contamina o seguinte."""
    import bot_telegram
    bot_telegram.EXECUCAO.update(rodando=False, inicio=None, quem=None,
                                 projeto=None)
    yield
    bot_telegram.EXECUCAO.update(rodando=False, inicio=None, quem=None,
                                 projeto=None)


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
                        lambda quem, chave: enviadas.append('RODOU'))

    bot_telegram.tratar({'message': {'text': 'bom dia pessoal',
                                     'from': {'first_name': 'Ana'}}})

    assert enviadas == []


def test_tratar_aceita_comando_com_nome_do_bot(monkeypatch):
    """Em grupo o Telegram entrega '/cota@nome_do_bot'."""
    import bot_telegram
    chamadas = []
    monkeypatch.setattr(bot_telegram, 'comando_rodar',
                        lambda quem, chave: chamadas.append((quem, chave)))

    bot_telegram.tratar({'message': {'text': '/cota@robo_siafi_bot',
                                     'from': {'first_name': 'Ana'}}})

    assert chamadas == [('Ana', 'cota')]


def test_tratar_reconhece_os_dois_robos(monkeypatch):
    """/cota e /credito acionam robos diferentes, em repositorios diferentes."""
    import bot_telegram
    chamadas = []
    monkeypatch.setattr(bot_telegram, 'comando_rodar',
                        lambda quem, chave: chamadas.append(chave))

    for comando in ('/cota', '/credito'):
        bot_telegram.tratar({'message': {'text': comando,
                                         'from': {'first_name': 'Ana'}}})

    assert chamadas == ['cota', 'credito']


def test_tratar_ignora_o_antigo_rodar(monkeypatch):
    """/rodar virou ambiguo com dois robos no grupo e foi retirado."""
    import bot_telegram
    chamadas = []
    monkeypatch.setattr(bot_telegram, 'comando_rodar',
                        lambda quem, chave: chamadas.append(chave))
    monkeypatch.setattr(bot_telegram, 'enviar', lambda *a, **kw: None)

    bot_telegram.tratar({'message': {'text': '/rodar',
                                     'from': {'first_name': 'Ana'}}})

    assert chamadas == []


def projetos_falsos(tmp_path):
    """Dois repositorios de mentira, cada um com a sua pasta data/."""
    projetos = {}
    for chave, nome in (('cota', 'Cota'), ('credito', 'Crédito')):
        repo = tmp_path / chave
        (repo / 'data').mkdir(parents=True)
        projetos[chave] = {'nome': nome, 'repo': str(repo)}
    return projetos


def test_caminhos_ultima_execucao_sem_arquivo(monkeypatch, tmp_path):
    import bot_telegram
    monkeypatch.setattr(bot_telegram, 'PROJETOS', projetos_falsos(tmp_path))

    assert bot_telegram.caminhos_ultima_execucao() == (None, None, None)


def test_caminhos_ultima_execucao_le_as_duas_linhas(monkeypatch, tmp_path):
    import bot_telegram
    projetos = projetos_falsos(tmp_path)
    monkeypatch.setattr(bot_telegram, 'PROJETOS', projetos)

    arquivo = tmp_path / 'cota' / 'data' / '.ultima_execucao'
    arquivo.write_text('/tmp/robo.log\n/tmp/relato.jsonl\n', encoding='utf-8')

    assert bot_telegram.caminhos_ultima_execucao() == (
        '/tmp/robo.log', '/tmp/relato.jsonl', 'Cota')


def test_log_entrega_a_execucao_mais_recente_entre_os_robos(monkeypatch, tmp_path):
    """Com dois robos, o /log tem que achar o log mais novo dos dois — e dizer
    de qual deles e."""
    import bot_telegram
    projetos = projetos_falsos(tmp_path)
    monkeypatch.setattr(bot_telegram, 'PROJETOS', projetos)

    antigo = tmp_path / 'cota' / 'data' / '.ultima_execucao'
    antigo.write_text('/tmp/cota.log\n/tmp/cota.jsonl\n', encoding='utf-8')
    os.utime(antigo, (1000, 1000))

    novo = tmp_path / 'credito' / 'data' / '.ultima_execucao'
    novo.write_text('/tmp/credito.log\n/tmp/credito.jsonl\n', encoding='utf-8')
    os.utime(novo, (2000, 2000))

    assert bot_telegram.caminhos_ultima_execucao() == (
        '/tmp/credito.log', '/tmp/credito.jsonl', 'Crédito')


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
    bot_telegram.EXECUCAO.update(rodando=True, inicio=time.time(), quem='Ana',
                                 projeto='Cota')

    bot_telegram.executar('Ana', 'cota')

    assert bot_telegram.EXECUCAO['rodando'] is False
    assert any('Falha ao executar' in m for m in enviadas)


def test_credito_e_recusado_enquanto_a_cota_roda(monkeypatch):
    """O caso que mais importa com dois robos: eles usam o MESMO usuario do
    SIAFI, entao /credito nao pode entrar enquanto /cota roda."""
    import bot_telegram
    enviadas = []
    threads_iniciadas = []
    monkeypatch.setattr(bot_telegram, 'enviar', enviadas.append)
    monkeypatch.setattr(bot_telegram.threading, 'Thread',
                        lambda *a, **kw: threads_iniciadas.append(kw))

    bot_telegram.EXECUCAO.update(rodando=True, inicio=time.time(), quem='Ana',
                                 projeto='Cota')
    bot_telegram.comando_rodar('Bruno', 'credito')

    assert threads_iniciadas == []
    assert any('Já tem execução do robô de Cota' in m for m in enviadas)
    assert any('iniciada por Ana' in m for m in enviadas)


# --- O laco de updates ------------------------------------------------------

GRUPO_TESTE = '-1004401529622'


def update_bruto(update_id, texto='/cota', idade_seg=0, chat=GRUPO_TESTE,
                 de=1296210429):
    return {'update_id': update_id, 'message': {
        'date': int(time.time()) - idade_seg,
        'chat': {'id': int(chat)},
        'from': {'id': de, 'first_name': 'Guilherme', 'is_bot': False},
        'text': texto}}


@pytest.fixture
def laco(monkeypatch):
    """Isola processar_updates: sem rede, sem disco, sem disparar o robo."""
    import bot_telegram
    disparos = []
    monkeypatch.setattr(bot_telegram, 'comando_rodar',
                        lambda quem, chave: disparos.append(quem))
    monkeypatch.setattr(bot_telegram, 'enviar', lambda *a, **kw: None)
    monkeypatch.setattr(bot_telegram, 'gravar_offset', lambda *a, **kw: None)
    monkeypatch.setattr(bot_telegram, 'CHAT_AUTORIZADO', GRUPO_TESTE)
    monkeypatch.setattr(bot_telegram, 'USUARIOS_AUTORIZADOS', [])
    return bot_telegram, disparos


def test_comando_antigo_nao_dispara_o_robo(laco):
    """O cenario mais perigoso: o bot fica fora do ar, um /rodar espera na fila
    do Telegram e e reentregue quando ele volta. O robo nao pode disparar."""
    bot, disparos = laco

    offset = bot.processar_updates([update_bruto(500, idade_seg=3600)])

    assert disparos == []
    # O offset avanca mesmo assim: senao o comando velho voltaria para sempre.
    assert offset == 501


def test_comando_recente_dispara_o_robo(laco):
    """Contraprova: sem isto, o teste acima passaria com o bot quebrado."""
    bot, disparos = laco

    offset = bot.processar_updates([update_bruto(600, idade_seg=5)])

    assert disparos == ['Guilherme']
    assert offset == 601


def test_comando_de_outro_chat_nao_dispara(laco):
    bot, disparos = laco

    bot.processar_updates([update_bruto(700, chat='-100999')])

    assert disparos == []


def test_usuario_fora_da_allowlist_nao_dispara(laco, monkeypatch):
    bot, disparos = laco
    monkeypatch.setattr(bot, 'USUARIOS_AUTORIZADOS', ['1296210429'])

    bot.processar_updates([update_bruto(800, de=999999)])

    assert disparos == []


def test_usuario_da_allowlist_dispara(laco, monkeypatch):
    bot, disparos = laco
    monkeypatch.setattr(bot, 'USUARIOS_AUTORIZADOS', ['1296210429'])

    bot.processar_updates([update_bruto(900, de=1296210429)])

    assert disparos == ['Guilherme']


def test_execucao_pelo_telegram_e_sempre_sem_janela(monkeypatch):
    """O x3270 depende do WSLg da sessao grafica; com a tela bloqueada, abrir
    janela nao e garantido. O disparo pelo Telegram e sempre desassistido,
    entao forca o s3270 (headless) mesmo que o .env peca janela.
    """
    import bot_telegram
    capturado = {}

    class ProcFalso:
        returncode = 0

        def poll(self):
            return 0

    def popen_falso(args, env=None, **kwargs):
        capturado['env'] = env
        return ProcFalso()

    monkeypatch.setattr(bot_telegram, 'enviar', lambda *a, **kw: None)
    monkeypatch.setattr(bot_telegram, 'ler_eventos', lambda *a, **kw: [])
    monkeypatch.setattr(bot_telegram, 'montar_final', lambda *a, **kw: 'fim')
    monkeypatch.setattr(bot_telegram.subprocess, 'Popen', popen_falso)
    monkeypatch.setenv('SIAFI_VISIVEL', 'true')

    bot_telegram.executar('Ana', 'cota')

    assert capturado['env']['SIAFI_VISIVEL'] == 'false'


def test_ambiente_do_projeto_nao_vaza_o_env_do_bot(monkeypatch):
    """O bot carrega o .env do repo de cota no proprio processo.

    Passar isso adiante fazia o robo de credito herdar o ONEDRIVE_BASE de cota
    e ir procurar as planilhas na pasta errada: o python-dotenv NAO sobrescreve
    variavel que ja existe no ambiente, entao o .env do credito perdia.
    """
    import bot_telegram
    monkeypatch.setenv('ONEDRIVE_BASE', '/pasta/da/cota')
    monkeypatch.setenv('COISA_DO_SISTEMA', 'preservado')
    monkeypatch.setattr(bot_telegram, 'CHAVES_DO_ENV', {'ONEDRIVE_BASE'})

    ambiente = bot_telegram.ambiente_do_projeto(ROBO_LOG='/tmp/x.log')

    assert 'ONEDRIVE_BASE' not in ambiente
    assert ambiente['COISA_DO_SISTEMA'] == 'preservado'
    assert ambiente['ROBO_LOG'] == '/tmp/x.log'
