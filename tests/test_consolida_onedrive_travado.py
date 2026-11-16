"""Arquivo travado no fim da consolidação: OneDrive sincronizando ou planilha
aberta no Excel.

O consolidado é salvo primeiro; depois as planilhas de origem são arquivadas e
o conferência antigo sai da pasta. Qualquer um desses passos pode falhar por
trava do Windows, e a execução seguinte precisa continuar de onde a anterior
parou, sem perder nem repetir linha.

Em 05/11/2026 08:43 o conferência do dia não pôde ser removido. O consolida.py
abortou, que é o certo, mas o motivo saiu só por print: o grupo recebeu apenas
'A consolidação das planilhas não passou'.

Pior era a trava cair numa planilha de origem: o conferência do dia já tinha
sido removido, e a execução seguinte criava um conferência novo só com as
planilhas que tinham sobrado, por cima do consolidado anterior. As linhas das
planilhas já arquivadas nunca chegavam ao SIAFI e as rodadas anteriores do dia
sumiam do arquivo.
"""
import os

import pandas as pd
import pytest

import consolida
# 'pastas' troca TODAS as constantes de pasta do consolida: sem ela o main()
# moveria arquivos do OneDrive de verdade.
from tests.test_coluna_pedido import (conferencia_de_hoje,  # noqa: F401
                                      devolver_para_a_conferencia,
                                      escrever_origem, ler_conferencia, pastas)


@pytest.fixture
def relatos(pastas, monkeypatch):
    registrados = []
    monkeypatch.setattr(consolida, 'relato',
                        lambda tipo, texto, **campos: registrados.append((tipo, texto)))
    return registrados


def erros(relatos):
    return [texto for tipo, texto in relatos if tipo == 'erro']


def nomes(pasta):
    return sorted(p.name for p in pasta.iterdir() if p.is_file())


def primeira_rodada_do_dia(pastas):
    """Uma rodada completa, como o login.py a deixa ao terminar: conferência
    devolvido à pasta de conferência e Realizados organizada."""
    escrever_origem(pastas.remanejamentos / 'A.xlsx', 2311, 4001)
    consolida.main()
    devolver_para_a_conferencia(pastas)
    organizados = pastas.realizados / 'Remanejamentos realizados'
    organizados.mkdir()
    (pastas.realizados / 'A.xlsx').rename(organizados / 'A.xlsx')


def travar(monkeypatch, funcao, quando):
    """Faz consolida.<funcao> falhar com PermissionError enquanto quando(...)
    for verdadeiro. Devolve o interruptor: destravar() volta ao normal."""
    original = getattr(consolida, funcao)
    estado = {'travado': True, 'chamadas': 0}

    def substituta(*args, **kwargs):
        estado['chamadas'] += 1
        if estado['travado'] and quando(estado['chamadas'], *args):
            raise PermissionError(13, 'Permission denied')
        return original(*args, **kwargs)

    monkeypatch.setattr(consolida, funcao, substituta)
    return lambda: estado.update(travado=False)


# --- conferência do dia travado (o caso de 05/11) ---------------------------

def test_conferencia_travado_avisa_o_grupo(pastas, relatos, monkeypatch):
    primeira_rodada_do_dia(pastas)
    escrever_origem(pastas.remanejamentos / 'B.xlsx', 1501, 4485)
    travar(monkeypatch, 'remover_com_retry', lambda n, *a: True)

    with pytest.raises(SystemExit) as saida:
        consolida.main()

    assert saida.value.code == 1
    assert len(erros(relatos)) == 1
    assert 'OneDrive' in erros(relatos)[0]
    assert 'acione de novo' in erros(relatos)[0]


def test_depois_do_conferencia_travado_a_execucao_seguinte_continua(
        pastas, relatos, monkeypatch):
    primeira_rodada_do_dia(pastas)
    escrever_origem(pastas.remanejamentos / 'B.xlsx', 1501, 4485)
    destravar = travar(monkeypatch, 'remover_com_retry', lambda n, *a: True)
    with pytest.raises(SystemExit):
        consolida.main()

    destravar()
    consolida.main()

    df = ler_conferencia(pastas)
    assert sorted(zip(df['Execução'], df['Pedido'])) == [(1, 'A'), (2, 'B')]
    assert nomes(pastas.conferencia) == []
    assert nomes(pastas.remanejamentos) == []
    assert any(tipo == 'planilha' and 'retomada' in texto.lower()
               for tipo, texto in relatos)


# --- planilha de origem travada ---------------------------------------------

def segunda_planilha_trava(chamada, origem, destino, *resto):
    """A primeira planilha é arquivada; a segunda está 'aberta no Excel'."""
    return destino == consolida.REALIZADOS and chamada >= 2


def test_planilha_travada_avisa_o_grupo_em_vez_de_estourar(pastas, relatos, monkeypatch):
    escrever_origem(pastas.remanejamentos / 'B.xlsx', 1501, 4485)
    travar(monkeypatch, 'mover_com_seguranca',
           lambda chamada, origem, destino, *r: destino == consolida.REALIZADOS)

    with pytest.raises(SystemExit) as saida:
        consolida.main()

    assert saida.value.code == 1
    assert len(erros(relatos)) == 1
    assert 'B.xlsx' in erros(relatos)[0]
    assert 'aberta no Excel' in erros(relatos)[0]
    assert 'acione de novo' in erros(relatos)[0]


def test_planilha_travada_nao_faz_perder_as_que_ja_tinham_sido_arquivadas(
        pastas, relatos, monkeypatch):
    primeira_rodada_do_dia(pastas)
    escrever_origem(pastas.remanejamentos / 'B.xlsx', 1501, 4485)
    escrever_origem(pastas.remanejamentos / 'C.xlsx', 1251, 4365)
    destravar = travar(monkeypatch, 'mover_com_seguranca', segunda_planilha_trava)
    with pytest.raises(SystemExit):
        consolida.main()
    # Uma das duas foi arquivada e a outra ficou presa na fila.
    assert len(nomes(pastas.remanejamentos)) == 1
    assert len(nomes(pastas.realizados)) == 1

    destravar()
    escrever_origem(pastas.remanejamentos / 'D.xlsx', 2101, 2500)   # chegou depois
    consolida.main()

    # Nenhuma linha perdida, nenhuma repetida, e a rodada da manhã continua lá.
    df = ler_conferencia(pastas)
    assert sorted(zip(df['Execução'], df['Pedido'])) == [(1, 'A'), (2, 'B'), (2, 'C')]
    assert nomes(pastas.realizados) == ['B.xlsx', 'C.xlsx']
    assert nomes(pastas.conferencia) == []
    # A planilha nova não entrou no arquivo que já estava pronto: fica para a
    # próxima execução.
    assert nomes(pastas.remanejamentos) == ['D.xlsx']


def test_se_nada_foi_arquivado_a_execucao_seguinte_consolida_do_zero(
        pastas, relatos, monkeypatch):
    """Nada irreversível aconteceu: vale a planilha como estiver na hora de
    rodar de novo, inclusive se alguém a corrigiu no meio-tempo."""
    primeira_rodada_do_dia(pastas)
    escrever_origem(pastas.remanejamentos / 'B.xlsx', 1501, 4485)
    destravar = travar(monkeypatch, 'mover_com_seguranca',
                       lambda chamada, origem, destino, *r: destino == consolida.REALIZADOS)
    with pytest.raises(SystemExit):
        consolida.main()
    assert nomes(pastas.remanejamentos) == ['B.xlsx']

    escrever_origem(pastas.remanejamentos / 'B.xlsx', 1501, 9999)   # corrigida
    destravar()
    consolida.main()

    df = ler_conferencia(pastas)
    assert sorted(zip(df['Execução'], df['Pedido'], df['Ação'])) == [
        (1, 'A', 4001), (2, 'B', 9999)]
    assert nomes(pastas.realizados) == ['B.xlsx']
    assert nomes(pastas.conferencia) == []


# --- sobra que o robô não sabe explicar -------------------------------------

def test_conferencia_parado_na_entrada_sem_explicacao_nao_vai_ao_siafi(
        pastas, relatos):
    """Um conferência na pasta de entrada cujas planilhas não estão na fila nem
    em Realizados: pode ter sido posto ali à mão, ou as planilhas dele podem ter
    sido retiradas de propósito. O robô não decide sozinho."""
    sobra = pastas.saida / 'Conferencia arquivo robo 01.01.xlsx'
    pd.DataFrame(
        [[1, 'X', 2311, 3, 0, 10, 1, 4001, 'x', None, None, 100.0, None, None]],
        columns=consolida.COLUNAS_CONFERENCIA).to_excel(sobra, index=False)
    escrever_origem(pastas.remanejamentos / 'B.xlsx', 1501, 4485)

    with pytest.raises(SystemExit) as saida:
        consolida.main()

    assert saida.value.code == 1
    assert len(erros(relatos)) == 1
    assert 'Conferencia arquivo robo 01.01.xlsx' in erros(relatos)[0]
    assert 'Robo (IPU 2)' in erros(relatos)[0]
    # Nada foi mexido.
    assert sobra.exists()
    assert nomes(pastas.remanejamentos) == ['B.xlsx']
    assert nomes(pastas.realizados) == []
    assert os.listdir(pastas.conferencia) == []
