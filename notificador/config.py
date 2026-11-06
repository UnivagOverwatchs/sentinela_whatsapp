"""
config.py - Configuração lida do ambiente (.env).

Banco: o mesmo PostgreSQL do Sentinela. Use DATABASE_URL ou as variáveis padrão
PGHOST / PGPORT / PGDATABASE / PGUSER / PGPASSWORD (o psycopg lê sozinho).
"""

import os
from dataclasses import dataclass, field


def _bool(nome: str, padrao: bool = False) -> bool:
    return os.getenv(nome, str(padrao)).strip().lower() in {"1", "true", "sim", "yes", "on"}


def _int(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, padrao))
    except ValueError:
        return padrao


@dataclass
class Config:
    # API do WhatsApp (projeto whatsapp-api / whatsapp-web.js)
    whatsapp_url: str = field(default_factory=lambda: os.getenv("WHATSAPP_API_URL", "http://localhost:3000").rstrip("/"))
    sessao: str = field(default_factory=lambda: os.getenv("WHATSAPP_SESSAO", "ABCD"))
    api_key: str = field(default_factory=lambda: os.getenv("WHATSAPP_API_KEY", ""))

    # De onde vem a foto do alerta: API do Sentinela e/ou pasta local do projeto DetectHumans.
    sentinela_api_url: str = field(default_factory=lambda: os.getenv("SENTINELA_API_URL", "http://localhost:8000").rstrip("/"))
    sentinela_pasta: str = field(default_factory=lambda: os.getenv("SENTINELA_PASTA", ""))
    # Link do painel incluído na mensagem (opcional).
    painel_url: str = field(default_factory=lambda: os.getenv("SENTINELA_PAINEL_URL", ""))

    # Telefones salvos sem DDD/país recebem estes valores.
    ddd_padrao: str = field(default_factory=lambda: os.getenv("TELEFONE_DDD_PADRAO", "65"))
    pais: str = field(default_factory=lambda: os.getenv("TELEFONE_PAIS", "55"))

    # Laço
    intervalo_s: int = field(default_factory=lambda: _int("NOTIF_INTERVALO_S", 3))
    # Só alertas desta janela: ao ligar o serviço, alertas antigos não disparam mensagens.
    janela_min: int = field(default_factory=lambda: _int("NOTIF_JANELA_MIN", 10))
    max_tentativas: int = field(default_factory=lambda: _int("NOTIF_MAX_TENTATIVAS", 3))
    # Modo teste: faz tudo (resolve números, registra), mas NÃO envia mensagens.
    modo_teste: bool = field(default_factory=lambda: _bool("NOTIF_MODO_TESTE"))
