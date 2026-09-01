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

from telegram_mensagens import (autorizado, formatar_duracao, ler_lista_de_ids,
                                montar_final, montar_progresso, muito_antigo,
                                pode_rodar, redigir)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_OFFSET = os.path.join(REPO, 'data', '.telegram_offset')

load_dotenv(os.path.join(REPO, '.env'))

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_AUTORIZADO = os.getenv('TELEGRAM_CHAT_ID')
API = f'https://api.telegram.org/bot{TOKEN}'
SEGREDOS = [os.getenv('SENHA'), os.getenv('USUARIO')]

# Vazia = qualquer membro do grupo aciona o robo. Preenchida = so estes ids.
USUARIOS_AUTORIZADOS = ler_lista_de_ids(
    os.getenv('TELEGRAM_USUARIOS_AUTORIZADOS'))

# Robos que o bot aciona. O de credito vive em outro repositorio; os dois
# entram no SIAFI com o MESMO usuario, e o lock compartilhado do rodar.sh
# garante que nunca rodem ao mesmo tempo.
PROJETOS = {
    'cota': {'nome': 'Cota', 'repo': REPO},
    'credito': {
        'nome': 'Crédito',
        'repo': os.path.expanduser(
            os.getenv('REPO_CREDITO', '~/code/splor-mg/siafi-automacao-credito')),
    },
}

AJUDA = (
    'Robô SIAFI\n\n'
    '/cota — aprovação e anulação de cota orçamentária\n'
    '/credito — solicitações de crédito\n'
    '/status — diz se há execução em andamento\n'
    '/log — envia o log completo da última execução\n'
    '/ajuda — esta mensagem\n\n'
    'Os dois robôs usam o mesmo usuário do SIAFI, então nunca rodam juntos.'
)

def _chaves_do_env(caminho):
    """Nomes das variaveis definidas no .env deste repositorio."""
    chaves = set()
    try:
        with open(caminho, encoding='utf-8') as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith('#') and '=' in linha:
                    chaves.add(linha.split('=', 1)[0].strip())
    except OSError:
        pass
    return chaves


CHAVES_DO_ENV = _chaves_do_env(os.path.join(REPO, '.env'))


def ambiente_do_projeto(**extra):
    """Ambiente do subprocesso, limpo das variaveis do .env do bot.

    O load_dotenv acima despejou o .env do repo de cota dentro deste processo.
    Repassar isso ao robo de credito fazia ele herdar o ONEDRIVE_BASE de cota e
    procurar as planilhas na pasta errada — porque o python-dotenv NAO
    sobrescreve variavel ja existente no ambiente, entao o .env dele perdia.

    Removendo essas chaves, cada robo carrega a propria configuracao. De
    quebra, o token do Telegram nao viaja para dentro do robo.
    """
    ambiente = {k: v for k, v in os.environ.items() if k not in CHAVES_DO_ENV}
    ambiente.update(extra)
    return ambiente


EXECUCAO = {'rodando': False, 'inicio': None, 'quem': None, 'projeto': None}
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
        r = requests.post(f'{API}/sendDocument', timeout=60,
                          data={'chat_id': CHAT_AUTORIZADO},
                          files={'document': (nome, conteudo.encode('utf-8'))})
        if r.status_code != 200:
            print(f'[aviso] Telegram recusou o documento ({r.status_code}): {r.text}')
            enviar(f'Não consegui enviar o log ({r.status_code}). '
                   f'Ele está no servidor em: {caminho}')
    except Exception as e:
        print(f'[aviso] falha ao enviar documento: {e}')
        enviar(f'Não consegui enviar o log: {e}')


def caminhos_ultima_execucao():
    """(log, relato, nome) da execucao mais recente entre todos os robos.

    Cada repositorio grava o seu .ultima_execucao quando pega o lock; o /log
    entrega o mais recente dos dois. Ler do disco (em vez de guardar em
    memoria) faz o comando continuar funcionando depois de um restart.
    """
    melhor = None
    for proj in PROJETOS.values():
        arquivo = os.path.join(proj['repo'], 'data', '.ultima_execucao')
        try:
            with open(arquivo, encoding='utf-8') as f:
                linhas = [l.strip() for l in f if l.strip()]
            candidato = (os.path.getmtime(arquivo), linhas[0], linhas[1],
                         proj['nome'])
        except (OSError, IndexError):
            continue
        if melhor is None or candidato[0] > melhor[0]:
            melhor = candidato

    if melhor is None:
        return None, None, None
    return melhor[1], melhor[2], melhor[3]


def executar(quem, chave):
    """Roda o rodar.sh e publica os marcos no grupo.

    Roda numa thread para o loop de polling continuar respondendo /status
    durante os minutos que o robo leva.
    """
    projeto = PROJETOS[chave]
    inicio = time.time()
    carimbo = datetime.now().strftime('%Y%m%d-%H%M%S')

    # O bot define os caminhos em vez de descobri-los depois: assim nao ha
    # risco de ler o relato da execucao ANTERIOR enquanto esta ainda comeca.
    logs = os.path.join(projeto['repo'], 'data', 'logs')
    log = os.path.join(logs, f'robo-{carimbo}.log')
    arquivo_relato = os.path.join(logs, f'relato-{carimbo}.jsonl')

    try:
        # SIAFI_VISIVEL=false a forca: o x3270 abre janela grafica via WSLg,
        # que depende da sessao grafica estar ativa. Com a tela do Windows
        # bloqueada isso nao e garantido, e o disparo pelo Telegram e sempre
        # desassistido. O duplo-clique no robo.bat continua respeitando o .env.
        ambiente = ambiente_do_projeto(ROBO_LOG=log,
                                       RELATO_ARQUIVO=arquivo_relato,
                                       SIAFI_VISIVEL='false')

        enviar(f'Robô SIAFI · {projeto["nome"]} · iniciado\npor {quem} · '
               f'{datetime.now().strftime("%d/%m às %H:%M")}')

        proc = subprocess.Popen(['bash', os.path.join(projeto['repo'], 'rodar.sh')],
                                env=ambiente,
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
            enviar('Já existe uma execução em andamento. Cota e crédito usam o '
                   'mesmo usuário do SIAFI e não rodam ao mesmo tempo.')
        else:
            enviar(montar_final(ler_eventos(arquivo_relato), codigo,
                                time.time() - inicio, nome=projeto['nome']))

    except Exception as e:
        # Sem isto, o EXECUCAO ficaria preso em rodando=True e todo /rodar
        # futuro seria recusado ate alguem reiniciar o servico — sem ninguem
        # no grupo entender por que.
        print(f'[erro] falha ao executar o robo: {e}')
        enviar(f'Falha ao executar o robô de {projeto["nome"]}: {e}\n'
               f'O log desta tentativa, se houver, está em {os.path.basename(log)}.')

    finally:
        with TRAVA:
            EXECUCAO.update(rodando=False, inicio=None, quem=None,
                            projeto=None)


def comando_rodar(quem, chave):
    with TRAVA:
        if EXECUCAO['rodando']:
            desde = datetime.fromtimestamp(EXECUCAO['inicio']).strftime('%H:%M')
            enviar(f'Já tem execução do robô de {EXECUCAO["projeto"]} em '
                   f'andamento desde {desde}, iniciada por {EXECUCAO["quem"]}.')
            return
        EXECUCAO.update(rodando=True, inicio=time.time(), quem=quem,
                        projeto=PROJETOS[chave]['nome'])

    threading.Thread(target=executar, args=(quem, chave), daemon=True).start()


def comando_status():
    with TRAVA:
        rodando, inicio, quem, projeto = (EXECUCAO['rodando'], EXECUCAO['inicio'],
                                          EXECUCAO['quem'], EXECUCAO['projeto'])

    if rodando:
        enviar(f'Robô de {projeto} em andamento há '
               f'{formatar_duracao(time.time() - inicio)}, iniciada por {quem}.')
        return

    log, _relato, nome = caminhos_ultima_execucao()
    if not log or not os.path.exists(log):
        enviar('Nenhuma execução registrada ainda. Use /cota ou /credito.')
        return

    quando = datetime.fromtimestamp(os.path.getmtime(log))
    enviar(f'Nenhuma execução em andamento. A última foi do robô de {nome}, '
           f'e terminou em {quando.strftime("%d/%m às %H:%M")}.')


def comando_log():
    log, _relato, nome = caminhos_ultima_execucao()
    if not log or not os.path.exists(log):
        enviar('Não há log de execução ainda.')
        return
    enviar(f'Log da última execução (robô de {nome}):')
    enviar_documento(log, os.path.basename(log))


def tratar(update):
    msg = update['message']
    quem = msg.get('from', {}).get('first_name', 'alguém')
    texto = (msg.get('text') or '').split('@')[0].strip().lower()

    if texto.lstrip('/') in PROJETOS:
        chave = texto.lstrip('/')
        if not pode_rodar(update, USUARIOS_AUTORIZADOS):
            # Responde em vez de ignorar: quem manda isto esta legitimamente no
            # grupo, e o silencio so viraria chamado de suporte.
            print(f'[info] {texto} recusado: {quem} nao esta na allowlist')
            enviar(f'{quem}, você não está na lista de quem pode acionar o '
                   'robô. Fale com quem administra o bot.')
            return
        print(f'[{datetime.now():%Y-%m-%d %H:%M:%S}] {texto} acionado por {quem}')
        comando_rodar(quem, chave)
    elif texto == '/status':
        comando_status()
    elif texto == '/log':
        comando_log()
    elif texto in ('/ajuda', '/start', '/help'):
        enviar(AJUDA)


def processar_updates(updates):
    """Trata um lote de updates e devolve o offset novo (None se veio vazio).

    Separada do main() para ser testavel sem rede: e aqui que mora a decisao de
    descartar comando antigo, o unico ponto que impede o robo de disparar
    sozinho depois de o bot ficar fora do ar.
    """
    offset = None

    for update in updates:
        # Confirma ANTES de tratar. Se o bot cair no meio do tratamento, o
        # comando nao volta na proxima consulta: um /rodar reentregue
        # dispararia o robo sozinho.
        offset = update['update_id'] + 1
        try:
            gravar_offset(offset)
        except OSError as e:
            # Nao derruba o bot: o offset em memoria ja avancou, entao esta
            # execucao nao reprocessa o update. Um restart pode reentregar,
            # mas o filtro de idade limita a janela.
            print(f'[aviso] nao foi possivel gravar o offset: {e}')

        if not autorizado(update, CHAT_AUTORIZADO):
            continue
        if muito_antigo(update, agora=time.time()):
            print('[info] comando antigo descartado')
            continue

        try:
            tratar(update)
        except Exception as e:
            print(f'[erro] falha ao tratar update: {e}')

    return offset


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

        novo_offset = processar_updates(updates)
        if novo_offset is not None:
            offset = novo_offset


if __name__ == '__main__':
    main()
