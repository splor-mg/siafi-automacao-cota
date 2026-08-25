"""Bot do Telegram que aciona o robo SIAFI.

Long-polling contra a API do Telegram: dispensa IP publico, porta aberta e
tunel. Roda como servico systemd dentro do WSL da maquina que tem o OneDrive
montado e o acesso de rede ao SIAFI.
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_OFFSET = os.path.join(REPO, 'data', '.telegram_offset')


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
