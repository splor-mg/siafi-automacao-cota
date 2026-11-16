"""'Print' da tela do SIAFI, em texto, para o log.

E o equivalente a selecionar tudo e copiar no terminal: as 24 linhas de 80
colunas, com a regua de colunas e o numero de cada linha — as mesmas
coordenadas que o fill_field() e o string_get() usam. Serve para entender por
que o SIAFI nao foi para a tela que o robo esperava: sem isto o log so trazia
'Keyboard locked', que e o sintoma (o robo tentou digitar numa posicao
protegida), nunca a mensagem do SIAFI que explica a causa.

Para achar todos os prints ja tirados:
    grep -A 28 "TELA DO SIAFI" data/logs/robo-*.log
"""

LINHAS = 24
COLUNAS = 80

# ....:....1....:....2 ... para localizar a coluna de um campo de relance
_REGUA = ''.join(
    str(c // 10) if c % 10 == 0 else (':' if c % 5 == 0 else '.')
    for c in range(1, COLUNAS + 1)
)

_TECLADO = {b'U': 'livre', b'L': 'travado', b'E': 'travado por erro'}


def ler_tela(em):
    """As 24 linhas da tela. Lista vazia se o emulador nao responder.

    Ler a tela nao depende do teclado: funciona mesmo depois de um 'Keyboard
    locked' (conferido no s3270 real).
    """
    try:
        return [em.string_get(l, 1, COLUNAS).rstrip()
                for l in range(1, LINHAS + 1)]
    except Exception:
        return []


def _estado(em):
    """Teclado e posicao do cursor, da linha de status do emulador.

    O cursor e o dado mais util depois de um 'Keyboard locked': mostra em que
    linha e coluna o robo estava tentando digitar.
    """
    try:
        status = em.status
        teclado = _TECLADO.get(status.keyboard, status.keyboard)
        return (f"teclado {teclado} | cursor na linha "
                f"{int(status.cursor_row) + 1}, coluna "
                f"{int(status.cursor_col) + 1}")
    except Exception:
        return ''


def imprimir_tela(em, motivo):
    """Copia a tela inteira para o log e devolve as linhas lidas.

    Nunca levanta excecao: roda durante o tratamento de outra falha, e
    mascarar o erro original so atrapalharia o diagnostico.
    """
    linhas = ler_tela(em)

    print()
    print(f"  ----- TELA DO SIAFI: {motivo} -----")
    if not linhas:
        print("  (não foi possível ler a tela: o emulador não respondeu)")
    else:
        estado = _estado(em)
        if estado:
            print(f"  {estado}")
        print(f"      {_REGUA}")
        for numero, linha in enumerate(linhas, 1):
            print(f"  {numero:02d}| {linha}")
    print("  " + "-" * (COLUNAS + 4))

    return linhas
