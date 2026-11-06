"""
http_api.py - Pequena API HTTP do notificador (só biblioteca padrão, sem framework).

    GET  /saude      -> estado do serviço (último ciclo e sessão do WhatsApp). Sem token.
    POST /notificar  -> o Sentinela avisa que gravou um alerta; o laço acorda e envia na hora.
                        Exige "Authorization: Bearer <NOTIF_TOKEN>". Corpo opcional: {"alerta_id": 12}.

Por que o POST não envia direto? Quem envia é sempre o laço (uma única thread usando o banco),
o que evita mensagens duplicadas. O POST só "acorda" o laço; se ele se perder, a verificação
periódica do banco envia mesmo assim alguns segundos depois.
"""

import hmac
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("notificador.http")


def criar_servidor(notificador, porta: int, host: str = "0.0.0.0") -> ThreadingHTTPServer:
    token = notificador.cfg.token

    class Manipulador(BaseHTTPRequestHandler):
        def _responder(self, codigo: int, dados: dict) -> None:
            corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):  # noqa: N802 (nome exigido pelo http.server)
            if self.path != "/saude":
                return self._responder(404, {"erro": "rota não encontrada"})
            self._responder(200, {"whatsapp_conectado": notificador.whatsapp.conectado(),
                                  "modo_teste": notificador.cfg.modo_teste,
                                  "ultimo_ciclo": notificador.ultimo_ciclo})

        def do_POST(self):  # noqa: N802
            if self.path != "/notificar":
                return self._responder(404, {"erro": "rota não encontrada"})
            if not token:
                return self._responder(503, {"erro": "NOTIF_TOKEN não configurado"})
            recebido = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            # compare_digest: comparação em tempo constante (não vaza o token por tempo de resposta).
            if not hmac.compare_digest(recebido.encode(), token.encode()):
                return self._responder(401, {"erro": "token inválido"})
            tamanho = min(int(self.headers.get("Content-Length") or 0), 10_000)
            corpo = self.rfile.read(tamanho) if tamanho else b""
            try:
                alerta_id = json.loads(corpo or b"{}").get("alerta_id")
            except (ValueError, AttributeError):
                alerta_id = None
            log.info("Aviso do Sentinela recebido (alerta %s)", alerta_id or "?")
            notificador.acordar.set()
            self._responder(202, {"status": "agendado"})

        def log_message(self, formato, *args):  # silencia o log padrão (uma linha por requisição)
            pass

    return ThreadingHTTPServer((host, porta), Manipulador)


def iniciar_em_segundo_plano(notificador, porta: int) -> ThreadingHTTPServer:
    servidor = criar_servidor(notificador, porta)
    threading.Thread(target=servidor.serve_forever, name="http", daemon=True).start()
    log.info("API HTTP em :%s (GET /saude, POST /notificar%s)", porta, "" if notificador.cfg.token else " DESLIGADO: sem NOTIF_TOKEN")
    return servidor
