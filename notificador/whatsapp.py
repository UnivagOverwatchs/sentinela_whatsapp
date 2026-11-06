"""
whatsapp.py - Cliente da API REST "whatsapp-api" (github.com/chrishubert/whatsapp-api).

Rotas usadas (todas com a sessão no caminho, ex.: ABCD):
    GET  /session/status/{sessao}        a sessão está conectada?
    POST /client/getNumberId/{sessao}    número -> ID real no WhatsApp (ou null se não tiver WhatsApp)
    POST /client/sendMessage/{sessao}    envia texto (contentType=string) ou imagem (MessageMedia)

Autenticação: cabeçalho x-api-key (valor de API_KEY no .env da whatsapp-api).
"""

import base64
from typing import Optional

import requests

from .config import Config


class ErroWhatsApp(Exception):
    """Falha de comunicação ou resposta de erro da API do WhatsApp."""


class ClienteWhatsApp:
    def __init__(self, cfg: Config, sessao_http: Optional[requests.Session] = None):
        self.cfg = cfg
        self.http = sessao_http or requests.Session()
        if cfg.api_key:
            self.http.headers["x-api-key"] = cfg.api_key

    def _requisitar(self, metodo: str, caminho: str, json: Optional[dict] = None) -> dict:
        url = f"{self.cfg.whatsapp_url}{caminho}/{self.cfg.sessao}"
        try:
            resposta = self.http.request(metodo, url, json=json, timeout=30)
            dados = resposta.json()
        except (requests.RequestException, ValueError) as erro:
            raise ErroWhatsApp(f"{metodo} {caminho}: {erro}") from erro
        if resposta.status_code >= 400 or not dados.get("success", False):
            raise ErroWhatsApp(f"{metodo} {caminho}: HTTP {resposta.status_code} {dados.get('error') or dados}")
        return dados

    def conectado(self) -> bool:
        """True se a sessão do WhatsApp está pronta para enviar (QR já lido)."""
        try:
            return self._requisitar("GET", "/session/status").get("state") == "CONNECTED"
        except ErroWhatsApp:
            return False

    def id_whatsapp(self, numero: str) -> Optional[str]:
        """'5565998765432' -> '556598765432@c.us' (formato real) ou None se o número não tem WhatsApp."""
        resultado = self._requisitar("POST", "/client/getNumberId", {"number": numero}).get("result")
        return resultado.get("_serialized") if resultado else None

    def enviar_texto(self, chat_id: str, texto: str) -> None:
        self._requisitar("POST", "/client/sendMessage",
                         {"chatId": chat_id, "contentType": "string", "content": texto})

    def enviar_imagem(self, chat_id: str, jpeg: bytes, legenda: str) -> None:
        self._requisitar("POST", "/client/sendMessage", {
            "chatId": chat_id,
            "contentType": "MessageMedia",
            "content": {"mimetype": "image/jpeg", "data": base64.b64encode(jpeg).decode("ascii"),
                        "filename": "alerta.jpg"},
            "options": {"caption": legenda},
        })
