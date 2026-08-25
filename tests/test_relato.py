import pytest

from relato import formatar_valor


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
