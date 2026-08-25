import json

import pytest

from relato import formatar_valor, relato


@pytest.mark.parametrize('centavos, esperado', [
    (7400000,   'R$ 74.000,00'),
    (50000000,  'R$ 500.000,00'),
    (0,         'R$ 0,00'),
    (5,         'R$ 0,05'),
    (123,       'R$ 1,23'),
    (100,       'R$ 1,00'),
    (-7400000,  '-R$ 74.000,00'),
])
def test_formatar_valor(centavos, esperado):
    assert formatar_valor(centavos) == esperado


def test_formatar_valor_aceita_string():
    """A planilha as vezes entrega o valor como texto."""
    assert formatar_valor('7400000') == 'R$ 74.000,00'


def test_relato_imprime_no_console_e_nao_quebra_sem_arquivo(capsys, monkeypatch):
    """Sem RELATO_ARQUIVO (execucao manual, fora do bot) so imprime."""
    monkeypatch.delenv('RELATO_ARQUIVO', raising=False)
    relato('login', 'Login no SIAFI realizado')
    assert capsys.readouterr().out == 'Login no SIAFI realizado\n'


def test_relato_grava_evento_no_jsonl(tmp_path, monkeypatch):
    arquivo = tmp_path / 'relato.jsonl'
    monkeypatch.setenv('RELATO_ARQUIVO', str(arquivo))

    relato('linha', 'Processando linha 4', linha=4, uo='1261')

    eventos = [json.loads(l) for l in arquivo.read_text(encoding='utf-8').splitlines()]
    assert len(eventos) == 1
    assert eventos[0]['tipo'] == 'linha'
    assert eventos[0]['texto'] == 'Processando linha 4'
    assert eventos[0]['linha'] == 4
    assert eventos[0]['uo'] == '1261'
    assert 'ts' in eventos[0]


def test_relato_acumula_eventos_na_ordem(tmp_path, monkeypatch):
    arquivo = tmp_path / 'relato.jsonl'
    monkeypatch.setenv('RELATO_ARQUIVO', str(arquivo))

    relato('login', 'Login no SIAFI realizado')
    relato('pendentes', '2 linha(s) pendente(s)', linhas=[4, 5])

    eventos = [json.loads(l) for l in arquivo.read_text(encoding='utf-8').splitlines()]
    assert [e['tipo'] for e in eventos] == ['login', 'pendentes']
    assert eventos[1]['linhas'] == [4, 5]


def test_relato_cria_a_pasta_se_nao_existir(tmp_path, monkeypatch):
    arquivo = tmp_path / 'logs' / 'relato.jsonl'
    monkeypatch.setenv('RELATO_ARQUIVO', str(arquivo))

    relato('login', 'Login no SIAFI realizado')

    assert arquivo.exists()
