"""Separa a mensagem destinada ao usuario da saida de diagnostico.

O robo continua imprimindo tudo no console (a janela do robo.bat fica igual a
de hoje). Alem disso, os eventos que interessam a quem acompanha pelo Telegram
sao gravados num .jsonl que o bot le. O bot nunca le o stdout bruto: assim um
print() de debug futuro nao vaza para o grupo.
"""


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
