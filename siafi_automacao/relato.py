"""Separa a mensagem destinada ao usuario da saida de diagnostico.

O robo continua imprimindo tudo no console (a janela do robo.bat fica igual a
de hoje). Alem disso, os eventos que interessam a quem acompanha pelo Telegram
sao gravados num .jsonl que o bot le. O bot nunca le o stdout bruto: assim um
print() de debug futuro nao vaza para o grupo.
"""

import json
import os
from datetime import datetime


def formatar_valor(centavos):
    """Converte o inteiro em centavos da planilha para reais.

    A planilha guarda o valor no formato do mainframe, sem separador decimal:
    7400000 significa R$ 74.000,00.
    """
    n = int(centavos)
    sinal = '-' if n < 0 else ''
    inteiros, cents = divmod(abs(n), 100)
    milhar = f'{inteiros:,}'.replace(',', '.')
    return f'{sinal}R$ {milhar},{cents:02d}'


def relato(tipo, texto, **campos):
    """Imprime no console e, se houver execucao instrumentada, grava o evento.

    O caminho do arquivo vem da variavel de ambiente RELATO_ARQUIVO, definida
    pelo rodar.sh. Usar variavel de ambiente (em vez de parametro) faz o
    consolida.py, que roda como subprocesso do login.py, herdar o mesmo arquivo
    sem precisar receber nada.
    """
    print(texto)

    caminho = os.getenv('RELATO_ARQUIVO')
    if not caminho:
        return

    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)

    evento = {
        'tipo': tipo,
        'ts': datetime.now().isoformat(timespec='seconds'),
        'texto': texto,
    }
    evento.update(campos)

    with open(caminho, 'a', encoding='utf-8') as f:
        f.write(json.dumps(evento, ensure_ascii=False) + '\n')
