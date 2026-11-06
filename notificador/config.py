"""
config.py - Configuração lida do ambiente (.env).

Banco: o mesmo PostgreSQL do Sentinela. Use DATABASE_URL ou as variáveis padrão
PGHOST / PGPORT / PGDATABASE / PGUSER / PGPASSWORD (o psycopg lê sozinho).
"""

import os
import re
from dataclasses import dataclass, field


def _env(nome: str, padrao: str = "") -> str:
    """
    Lê a variável e remove comentário no fim da linha ("true   # explicação").
    Necessário porque o env_file do Docker Compose NÃO remove esses comentários
    (o python-dotenv remove): sem isso, NOTIF_MODO_TESTE=true virava "false" no container.
    """
    return re.sub(r"\s+#.*$", "", os.getenv(nome, padrao)).strip()


def _bool(nome: str, padrao: bool = False) -> bool:
    return _env(nome, str(padrao)).lower() in {"1", "true", "sim", "yes", "on"}


def _int(nome: str, padrao: int) -> int:
    try:
        return int(_env(nome, str(padrao)))
    except ValueError:
        return padrao


@dataclass
class Config:
    # API do WhatsApp (projeto whatsapp-api / whatsapp-web.js)
    whatsapp_url: str = field(default_factory=lambda: _env("WHATSAPP_API_URL", "http://localhost:3000").rstrip("/"))
    sessao: str = field(default_factory=lambda: _env("WHATSAPP_SESSAO", "ABCD"))
    api_key: str = field(default_factory=lambda: _env("WHATSAPP_API_KEY", ""))

    # De onde vem a foto do alerta: API do Sentinela e/ou pasta local do projeto DetectHumans.
    sentinela_api_url: str = field(default_factory=lambda: _env("SENTINELA_API_URL", "http://localhost:8000").rstrip("/"))
    sentinela_pasta: str = field(default_factory=lambda: _env("SENTINELA_PASTA", ""))
    # Link do painel incluído na mensagem (opcional).
    painel_url: str = field(default_factory=lambda: _env("SENTINELA_PAINEL_URL", ""))

    # Telefones salvos sem DDD/país recebem estes valores.
    ddd_padrao: str = field(default_factory=lambda: _env("TELEFONE_DDD_PADRAO", "65"))
    pais: str = field(default_factory=lambda: _env("TELEFONE_PAIS", "55"))

    # Laço
    intervalo_s: int = field(default_factory=lambda: _int("NOTIF_INTERVALO_S", 3))
    # Só alertas desta janela: ao ligar o serviço, alertas antigos não disparam mensagens.
    janela_min: int = field(default_factory=lambda: _int("NOTIF_JANELA_MIN", 10))
    max_tentativas: int = field(default_factory=lambda: _int("NOTIF_MAX_TENTATIVAS", 3))
    # Modo teste: faz tudo (resolve números, registra), mas NÃO envia mensagens.
    modo_teste: bool = field(default_factory=lambda: _bool("NOTIF_MODO_TESTE"))

    # HTTP: o Sentinela (em outro servidor) chama POST /notificar para envio imediato.
    http_porta: int = field(default_factory=lambda: _int("NOTIF_HTTP_PORTA", 8100))
    # Token exigido no POST /notificar (cabeçalho Authorization: Bearer <token>). Vazio = POST desligado.
    token: str = field(default_factory=lambda: _env("NOTIF_TOKEN", ""))
