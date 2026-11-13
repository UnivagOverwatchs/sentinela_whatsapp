"""API HTTP do notificador: token, acordar o laço e /saude (servidor real em porta livre)."""
import json
import urllib.error
import urllib.request

import pytest

from notificador.config import Config
from notificador.http_api import iniciar_em_segundo_plano
from notificador.servico import Notificador


class WhatsAppFalso:
    def conectado(self):
        return True


@pytest.fixture
def ambiente():
    cfg = Config()
    cfg.token = "segredo-teste"
    notificador = Notificador(banco=None, whatsapp=WhatsAppFalso(), cfg=cfg, buscar_foto=lambda a: None)
    servidor = iniciar_em_segundo_plano(notificador, porta=0)  # porta 0 = o sistema escolhe uma livre
    yield notificador, f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()


def chamar(url, metodo="GET", token=None, corpo=None):
    req = urllib.request.Request(url, method=metodo, data=json.dumps(corpo).encode() if corpo else None)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_notificar_sem_token_e_recusado(ambiente):
    notificador, base = ambiente
    assert chamar(base + "/notificar", "POST")[0] == 401
    assert chamar(base + "/notificar", "POST", token="errado")[0] == 401
    assert not notificador.acordar.is_set()


def test_notificar_com_token_acorda_o_laco(ambiente):
    notificador, base = ambiente
    codigo, dados = chamar(base + "/notificar", "POST", token="segredo-teste", corpo={"alerta_id": 7})
    assert codigo == 202 and dados["status"] == "agendado"
    assert notificador.acordar.is_set()


def test_saude(ambiente):
    _, base = ambiente
    codigo, dados = chamar(base + "/saude")
    assert codigo == 200 and dados["whatsapp_conectado"] is True


def test_sem_token_configurado_post_fica_desligado():
    cfg = Config()
    cfg.token = ""
    n = Notificador(None, WhatsAppFalso(), cfg, lambda a: None)
    servidor = iniciar_em_segundo_plano(n, porta=0)
    try:
        assert chamar(f"http://127.0.0.1:{servidor.server_address[1]}/notificar", "POST", token="x")[0] == 503
    finally:
        servidor.shutdown()


def test_aviso_exige_token_e_texto(ambiente):
    _, base = ambiente
    assert chamar(base + "/aviso", "POST", corpo={"texto": "oi"})[0] == 401
    assert chamar(base + "/aviso", "POST", token="segredo-teste", corpo={"texto": "  "})[0] == 400
    assert chamar(base + "/aviso", "POST", token="segredo-teste", corpo={"texto": "x" * 1001})[0] == 400


def test_aviso_agenda_e_acorda_o_laco(ambiente):
    notificador, base = ambiente
    codigo, dados = chamar(base + "/aviso", "POST", token="segredo-teste", corpo={"texto": "Câmera Quarto 2 sem sinal"})
    assert codigo == 202 and dados["status"] == "agendado"
    assert notificador.acordar.is_set()
    assert notificador._avisos.get_nowait() == "Câmera Quarto 2 sem sinal"
