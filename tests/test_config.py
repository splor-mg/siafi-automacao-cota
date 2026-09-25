"""A lista de UOs bloqueadas decide o que NAO vai ao SIAFI.

Errar o parsing aqui nao aprova nada indevido (o efeito e sempre pular), mas
faria linhas ficarem sem processar sem ninguem entender por que.
"""
from config import ler_lista_de_uos


def test_le_lista_separada_por_virgula():
    assert ler_lista_de_uos('1101,1371,2091') == {'1101', '1371', '2091'}


def test_tolera_espacos():
    assert ler_lista_de_uos(' 1101 , 1371 ') == {'1101', '1371'}


def test_normaliza_como_a_planilha_entrega():
    """O UO_COD as vezes chega como 1101.0 do Excel."""
    assert ler_lista_de_uos('1101.0, 01371') == {'1101', '1371'}


def test_vazio_desliga_a_trava():
    """E assim que se desfaz o teste: esvaziar a variavel no .env."""
    assert ler_lista_de_uos('') == set()
    assert ler_lista_de_uos(None) == set()
    assert ler_lista_de_uos('   ') == set()
