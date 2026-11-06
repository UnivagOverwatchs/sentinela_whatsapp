"""
telefone.py - Converte o telefone digitado no cadastro para o formato do WhatsApp (só dígitos, com país).

Exemplos (DDD padrão 65, país 55):
    "(65) 99876-5432"   -> "5565998765432"
    "+55 65 3322-1100"  -> "556533221100"
    "99876-5432"        -> "5565998765432"   (sem DDD: usa o padrão)
    "0 65 99876-5432"   -> "5565998765432"   (zero de discagem é removido)
    "192"               -> None              (serviço de emergência: não tem WhatsApp)

O 9º dígito NÃO é mexido aqui: quem decide o ID correto é a própria API do WhatsApp
(getNumberId), porque números antigos podem estar registrados com ou sem ele.
"""

import re
from typing import Optional


def normalizar(telefone: str, ddd_padrao: str = "65", pais: str = "55") -> Optional[str]:
    digitos = re.sub(r"\D", "", telefone or "").lstrip("0")
    if digitos.startswith(pais) and len(digitos) in (12, 13):
        return digitos                      # já tem país + DDD
    if len(digitos) in (10, 11):
        return pais + digitos               # DDD + número
    if len(digitos) in (8, 9):
        return pais + ddd_padrao + digitos  # só o número
    return None                             # curto/longo demais (ex.: 192, 190)
