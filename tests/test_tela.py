"""O 'print' da tela do SIAFI que vai para o log quando algo da errado.

E a unica pista de por que o SIAFI nao foi para a tela que o robo esperava.
Roda sempre no tratamento de outra falha, entao nao pode levantar excecao.
"""
from tela import imprimir_tela, ler_tela


class Status:
    """A linha de status do py3270: tudo em bytes, cursor contado do zero."""
    keyboard = b'L'
    cursor_row = b'10'
    cursor_col = b'4'


class EmuladorComTela:
    def __init__(self, linhas, status=None):
        self.linhas = linhas
        if status is not None:
            self.status = status

    def string_get(self, linha, coluna, tamanho):
        return self.linhas.get(linha, '').ljust(tamanho)


class EmuladorMorto:
    def string_get(self, linha, coluna, tamanho):
        raise BrokenPipeError('emulador caiu')


TELA = {1: ' 0153- DOTACAO NAO CADASTRADA PARA A UO',
        11: '  04 122 705 2500 0001'}


def test_le_as_24_linhas_sem_os_espacos_do_fim():
    linhas = ler_tela(EmuladorComTela(TELA))

    assert len(linhas) == 24
    assert linhas[0] == ' 0153- DOTACAO NAO CADASTRADA PARA A UO'
    assert linhas[10] == '  04 122 705 2500 0001'
    assert linhas[23] == ''


def test_imprime_cada_linha_com_o_numero_e_a_regua_de_colunas(capsys):
    """Numero da linha e regua sao as coordenadas do fill_field(): e com elas
    que se descobre em que campo o robo estava."""
    linhas = imprimir_tela(EmuladorComTela(TELA), 'envio interrompido')

    saida = capsys.readouterr().out.splitlines()
    assert '  ----- TELA DO SIAFI: envio interrompido -----' in saida
    assert '  01|  0153- DOTACAO NAO CADASTRADA PARA A UO' in saida
    assert '  11|   04 122 705 2500 0001' in saida
    assert '  24| ' in saida

    regua = next(l for l in saida if l.lstrip().startswith('....:....1'))
    linha_11 = next(l for l in saida if l.startswith('  11|'))
    # a regua comeca na mesma coluna que o texto: '8' marca a coluna 80
    assert len(regua) == len('  11| ') + 80
    assert regua[len('  11| ') + 80 - 1] == '8'
    assert linha_11[len('  11| ') + 3 - 1] == '0'      # coluna 3 da tela
    assert len(linhas) == 24


def test_mostra_o_teclado_e_onde_o_cursor_estava(capsys):
    """Depois de um 'Keyboard locked' o cursor fica onde o robo tentou
    digitar. O py3270 conta do zero; o log mostra como o fill_field() conta."""
    imprimir_tela(EmuladorComTela(TELA, Status()), 'envio interrompido')

    assert ('teclado travado | cursor na linha 11, coluna 5'
            in capsys.readouterr().out)


def test_emulador_morto_nao_levanta_excecao(capsys):
    """Se a sessao caiu nao ha tela para ler, e o erro original e o que
    importa."""
    assert imprimir_tela(EmuladorMorto(), 'envio interrompido') == []
    assert 'não foi possível ler a tela' in capsys.readouterr().out
