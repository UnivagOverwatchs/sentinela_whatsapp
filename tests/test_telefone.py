"""Normalização de telefones brasileiros para o WhatsApp."""
import pytest

from notificador.telefone import normalizar


@pytest.mark.parametrize("entrada,esperado", [
    ("(65) 99876-5432", "5565998765432"),     # celular com DDD
    ("65 3322-1100", "556533221100"),         # fixo com DDD
    ("+55 (65) 99876-5432", "5565998765432"), # já com país
    ("5565998765432", "5565998765432"),
    ("99876-5432", "5565998765432"),          # sem DDD -> DDD padrão
    ("3322-1100", "556533221100"),
    ("0 65 99876-5432", "5565998765432"),     # zero de discagem
    ("192", None),                            # emergência: sem WhatsApp
    ("", None),
    (None, None),
])
def test_normalizar(entrada, esperado):
    assert normalizar(entrada, ddd_padrao="65", pais="55") == esperado
