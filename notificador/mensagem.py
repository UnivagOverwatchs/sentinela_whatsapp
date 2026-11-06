"""mensagem.py - Texto enviado no WhatsApp (formatação do WhatsApp: *negrito*, _itálico_)."""

from datetime import datetime
from typing import Any, Dict

TITULOS = {
    "QUEDA": "Queda detectada",
    "MOVIMENTO_ANOMALO": "Pessoa no chão",
}


def _formatar_horario(valor: Any) -> str:
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor)
    return valor.strftime("%d/%m/%Y às %H:%M:%S")


def montar_texto(alerta: Dict[str, Any], contato: Dict[str, Any], painel_url: str = "") -> str:
    titulo = TITULOS.get(alerta["tipo"], "Alerta")
    local = alerta["camera_nome"] + (f" ({alerta['camera_local']})" if alerta.get("camera_local") else "")
    linhas = [
        f"🚨 *SENTINELA — {titulo}*",
        "",
        f"Olá, {contato['nome']}.",
        f"📍 *Local:* {local}",
        f"🕒 *Horário:* {_formatar_horario(alerta['ocorrido_em'])}",
        "",
        "Verifique o residente imediatamente.",
    ]
    if painel_url:
        linhas.append(f"Painel: {painel_url}")
    return "\n".join(linhas)
