"""Retomar o conferência que ficou com linhas pendentes.

Quando o SIAFI recusa a conexão, a consolidação ja aconteceu: os originais
foram para Realizados e o conferência voltou para a pasta de conferência com
as linhas por fazer. Sem retomada, a execucao seguinte diz 'nada a consolidar'
e essas linhas ficam presas ate alguem mover o arquivo na mao.
"""
import pandas as pd

from consolida import contar_pendentes, retomar_conferencia_pendente

COLUNAS = ['Execução', 'UO_COD', 'Grupo', 'Ação', 'Aprovar', 'Progresso']


def escrever_conferencia(caminho, linhas):
    pd.DataFrame(linhas, columns=COLUNAS).to_excel(caminho, index=False)


def test_conta_linha_com_dados_e_sem_progresso(tmp_path):
    arq = tmp_path / 'Conferencia arquivo robo 02.09.xlsx'
    escrever_conferencia(arq, [
        [1, 1261, 3, 4511, 100, 'Ok'],
        [1, 1261, 3, 2128, 200, None],
        [1, 1451, 3, 4344, 300, None],
    ])

    assert contar_pendentes(str(arq)) == 2


def test_progresso_em_branco_conta_como_pendente(tmp_path):
    """Celula com espacos nao e 'preenchida'."""
    arq = tmp_path / 'Conferencia arquivo robo 02.09.xlsx'
    escrever_conferencia(arq, [[1, 1261, 3, 4511, 100, '   ']])

    assert contar_pendentes(str(arq)) == 1


def test_tudo_processado_nao_tem_pendencia(tmp_path):
    arq = tmp_path / 'Conferencia arquivo robo 02.09.xlsx'
    escrever_conferencia(arq, [
        [1, 1261, 3, 4511, 100, 'Ok'],
        [1, 1261, 3, 2128, 200, 'Saldo zerado na conta'],
    ])

    assert contar_pendentes(str(arq)) == 0


def test_retoma_movendo_o_conferencia_para_a_pasta_de_entrada(tmp_path):
    conferencia = tmp_path / 'Conferencia arquivo robo'
    entrada = tmp_path / 'Robo (IPU 2)' / 'Python'
    conferencia.mkdir()
    entrada.mkdir(parents=True)
    arq = conferencia / 'Conferencia arquivo robo 02.09.xlsx'
    escrever_conferencia(arq, [[1, 1261, 3, 4511, 100, None]])

    assert retomar_conferencia_pendente(str(conferencia), str(entrada)) is True

    assert list(conferencia.iterdir()) == []
    assert [p.name for p in entrada.iterdir()] == [
        'Conferencia arquivo robo 02.09.xlsx']


def test_nao_retoma_conferencia_ja_concluido(tmp_path):
    """Sem pendencia, mover o arquivo so o tiraria do lugar por nada."""
    conferencia = tmp_path / 'Conferencia arquivo robo'
    entrada = tmp_path / 'entrada'
    conferencia.mkdir()
    entrada.mkdir()
    arq = conferencia / 'Conferencia arquivo robo 02.09.xlsx'
    escrever_conferencia(arq, [[1, 1261, 3, 4511, 100, 'Ok']])

    assert retomar_conferencia_pendente(str(conferencia), str(entrada)) is False

    assert arq.exists()
    assert list(entrada.iterdir()) == []


def test_sem_conferencia_nenhum_nao_quebra(tmp_path):
    vazia = tmp_path / 'Conferencia arquivo robo'
    vazia.mkdir()

    assert retomar_conferencia_pendente(str(vazia), str(tmp_path)) is False
