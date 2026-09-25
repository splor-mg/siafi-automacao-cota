"""Leitura de configuracao que precisa de tratamento.

Fica separado do login.py porque la nada e importavel: o modulo executa o fluxo
inteiro no import, e isso deixaria estas regras sem teste.
"""


def ler_lista_de_uos(valor):
    """Converte '1101, 1371' do .env num conjunto de UOs normalizadas.

    Normaliza do mesmo jeito que o robo trata a coluna UO_COD da planilha
    (1101.0 -> '1101'), senao a comparacao falharia por causa de casa decimal
    ou zero a esquerda.

    Valor vazio devolve conjunto vazio — e assim que se desliga a trava.
    """
    uos = set()
    for pedaco in (valor or '').split(','):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        try:
            uos.add(str(int(float(pedaco))))
        except ValueError:
            uos.add(pedaco)
    return uos
