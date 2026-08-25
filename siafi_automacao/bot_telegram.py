"""Bot do Telegram que aciona o robo SIAFI.

Long-polling contra a API do Telegram: dispensa IP publico, porta aberta e
tunel. Roda como servico systemd dentro do WSL da maquina que tem o OneDrive
montado e o acesso de rede ao SIAFI.
"""
import json
import os
import subprocess
import threading
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

from telegram_mensagens import (autorizado, formatar_duracao, montar_final,
                                montar_progresso, muito_antigo, redigir)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_OFFSET = os.path.join(REPO, 'data', '.telegram_offset')

load_dotenv(os.path.join(REPO, '.env'))

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_AUTORIZADO = os.getenv('TELEGRAM_CHAT_ID')
API = f'https://api.telegram.org/bot{TOKEN}'
SEGREDOS = [os.getenv('SENHA'), os.getenv('USUARIO')]

ARQUIVO_ULTIMA = os.path.join(REPO, 'data', '.ultima_execucao')
RODAR = os.path.join(REPO, 'rodar.sh')

AJUDA = (
    'Robô SIAFI\n\n'
    '/rodar — executa o robô (consolida as planilhas e processa no SIAFI)\n'
    '/status — diz se há execução em andamento\n'
    '/log — envia o log completo da última execução\n'
    '/ajuda — esta mensagem'
)

EXECUCAO = {'rodando': False, 'inicio': None, 'quem': None}
TRAVA = threading.Lock()


def ler_offset(caminho=None):
    """Ultimo update_id ja confirmado, ou None se nao houver.

    Devolve None tambem em arquivo corrompido: perder o offset e chato (o
    Telegram reentrega o backlog, que o filtro de idade descarta), mas derrubar
    o bot no arranque seria pior.
    """
    caminho = caminho or ARQUIVO_OFFSET
    try:
        with open(caminho, encoding='utf-8') as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def gravar_offset(offset, caminho=None):
    caminho = caminho or ARQUIVO_OFFSET
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write(str(offset))


def ler_eventos(caminho):
    """Le o .jsonl do relato da execucao.

    Descarta linha incompleta: o bot le o arquivo enquanto o robo ainda escreve
    nele, entao a ultima linha pode estar pela metade.
    """
    eventos = []
    try:
        with open(caminho, encoding='utf-8') as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    eventos.append(json.loads(linha))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return eventos


def enviar(texto):
    """Manda uma mensagem para o grupo. Nunca levanta excecao: falha de rede
    aqui nao pode derrubar o bot nem interromper o robo.

    Se o Telegram recusar a mensagem (tipicamente HTML malformado), tenta de
    novo como texto puro. Sem isso, uma recusa passaria em silencio e a equipe
    simplesmente nao receberia o resultado da execucao.
    """
    texto = redigir(texto, SEGREDOS)
    try:
        r = requests.post(f'{API}/sendMessage', timeout=30, data={
            'chat_id': CHAT_AUTORIZADO,
            'text': texto,
            'parse_mode': 'HTML',
        })
        if r.status_code == 200:
            return
        print(f'[aviso] Telegram recusou a mensagem ({r.status_code}): {r.text}')
        print('[aviso] reenviando como texto puro')
        requests.post(f'{API}/sendMessage', timeout=30, data={
            'chat_id': CHAT_AUTORIZADO,
            'text': texto.replace('<pre>', '').replace('</pre>', ''),
        })
    except Exception as e:
        print(f'[aviso] falha ao enviar mensagem: {e}')


def enviar_documento(caminho, nome):
    """Envia um arquivo, com os segredos redigidos antes de sair."""
    try:
        with open(caminho, encoding='utf-8', errors='replace') as f:
            conteudo = redigir(f.read(), SEGREDOS)
        requests.post(f'{API}/sendDocument', timeout=60,
                      data={'chat_id': CHAT_AUTORIZADO},
                      files={'document': (nome, conteudo.encode('utf-8'))})
    except Exception as e:
        print(f'[aviso] falha ao enviar documento: {e}')
        enviar(f'Não consegui enviar o log: {e}')


def caminhos_ultima_execucao():
    """(log, relato) da execucao mais recente, ou (None, None).

    O rodar.sh grava esses caminhos assim que pega o lock.
    """
    try:
        with open(ARQUIVO_ULTIMA, encoding='utf-8') as f:
            linhas = [l.strip() for l in f if l.strip()]
        return linhas[0], linhas[1]
    except (OSError, IndexError):
        return None, None


def executar(quem):
    """Roda o rodar.sh e publica os marcos no grupo.

    Roda numa thread para o loop de polling continuar respondendo /status
    durante os minutos que o robo leva.
    """
    inicio = time.time()
    carimbo = datetime.now().strftime('%Y%m%d-%H%M%S')

    # O bot define os caminhos em vez de descobri-los depois: assim nao ha
    # risco de ler o relato da execucao ANTERIOR enquanto esta ainda comeca.
    log = os.path.join(REPO, 'data', 'logs', f'robo-{carimbo}.log')
    arquivo_relato = os.path.join(REPO, 'data', 'logs', f'relato-{carimbo}.jsonl')

    ambiente = dict(os.environ, ROBO_LOG=log, RELATO_ARQUIVO=arquivo_relato)

    enviar(f'Robô SIAFI · iniciado\npor {quem} · '
           f'{datetime.now().strftime("%d/%m às %H:%M")}')

    proc = subprocess.Popen(['bash', RODAR], env=ambiente,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)

    progresso_enviado = False
    while proc.poll() is None:
        time.sleep(2)
        if not progresso_enviado:
            msg = montar_progresso(ler_eventos(arquivo_relato))
            if msg:
                enviar(msg)
                progresso_enviado = True

    codigo = proc.returncode
    if codigo == 10:
        enviar('Já existe uma execução em andamento (iniciada pelo robo.bat).')
    else:
        enviar(montar_final(ler_eventos(arquivo_relato), codigo,
                            time.time() - inicio))

    with TRAVA:
        EXECUCAO.update(rodando=False, inicio=None, quem=None)


def comando_rodar(quem):
    with TRAVA:
        if EXECUCAO['rodando']:
            desde = datetime.fromtimestamp(EXECUCAO['inicio']).strftime('%H:%M')
            enviar(f'Já tem execução em andamento desde {desde}, '
                   f'iniciada por {EXECUCAO["quem"]}.')
            return
        EXECUCAO.update(rodando=True, inicio=time.time(), quem=quem)

    threading.Thread(target=executar, args=(quem,), daemon=True).start()


def comando_status():
    with TRAVA:
        rodando, inicio, quem = (EXECUCAO['rodando'], EXECUCAO['inicio'],
                                 EXECUCAO['quem'])

    if rodando:
        enviar(f'Execução em andamento há {formatar_duracao(time.time() - inicio)}, '
               f'iniciada por {quem}.')
        return

    log, _ = caminhos_ultima_execucao()
    if not log or not os.path.exists(log):
        enviar('Nenhuma execução registrada ainda. Use /rodar.')
        return

    quando = datetime.fromtimestamp(os.path.getmtime(log))
    enviar(f'Nenhuma execução em andamento. '
           f'A última terminou em {quando.strftime("%d/%m às %H:%M")}.')


def comando_log():
    log, _ = caminhos_ultima_execucao()
    if not log or not os.path.exists(log):
        enviar('Não há log de execução ainda.')
        return
    enviar_documento(log, os.path.basename(log))


def tratar(update):
    msg = update['message']
    quem = msg.get('from', {}).get('first_name', 'alguém')
    texto = (msg.get('text') or '').split('@')[0].strip().lower()

    if texto == '/rodar':
        print(f'[{datetime.now():%Y-%m-%d %H:%M:%S}] /rodar acionado por {quem}')
        comando_rodar(quem)
    elif texto == '/status':
        comando_status()
    elif texto == '/log':
        comando_log()
    elif texto in ('/ajuda', '/start', '/help'):
        enviar(AJUDA)


def main():
    if not TOKEN or not CHAT_AUTORIZADO:
        raise SystemExit('Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env')

    print(f'Bot iniciado. Grupo autorizado: {CHAT_AUTORIZADO}')
    offset = ler_offset()
    espera = 1

    while True:
        try:
            r = requests.get(f'{API}/getUpdates', timeout=40,
                             params={'offset': offset, 'timeout': 30})
            r.raise_for_status()
            updates = r.json().get('result', [])
            espera = 1
        except Exception as e:
            print(f'[aviso] falha ao consultar o Telegram: {e}')
            time.sleep(espera)
            espera = min(espera * 2, 60)
            continue

        for update in updates:
            # Confirma ANTES de tratar. Se o bot cair no meio do tratamento, o
            # comando nao volta na proxima consulta: um /rodar reentregue
            # dispararia o robo sozinho.
            offset = update['update_id'] + 1
            gravar_offset(offset)

            if not autorizado(update, CHAT_AUTORIZADO):
                continue
            if muito_antigo(update, agora=time.time()):
                print('[info] comando antigo descartado')
                continue

            try:
                tratar(update)
            except Exception as e:
                print(f'[erro] falha ao tratar update: {e}')


if __name__ == '__main__':
    main()
