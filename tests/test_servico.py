"""
Testes do laço de notificação com banco e WhatsApp FALSOS (sem rede, sem Postgres).
Verificam: para quem envia, o que registra e o que acontece em cada tipo de falha.
"""
from datetime import datetime

import pytest

from notificador.config import Config
from notificador.mensagem import montar_texto
from notificador.servico import Notificador
from notificador.whatsapp import ErroWhatsApp


def linha(alerta_id=1, contato_id=1, telefone="(65) 99876-5432", nome="Felipe", tipo="QUEDA", tentativas=0):
    return {"alerta_id": alerta_id, "tipo": tipo, "ocorrido_em": datetime(2026, 11, 6, 14, 32, 5),
            "imagem": "alertas_queda/x.jpg", "camera_nome": "Quarto 2", "camera_local": "1º andar",
            "contato_id": contato_id, "contato_nome": nome, "telefone": telefone, "tentativas": tentativas}


class BancoFalso:
    def __init__(self, pendencias):
        self._pendencias = pendencias
        self.registros = []

    def pendencias(self, janela_min, max_tentativas):
        return self._pendencias

    def registrar(self, alerta_id, contato_id, status, chat_id=None, erro=None):
        self.registros.append((alerta_id, contato_id, status, chat_id))


class WhatsAppFalso:
    def __init__(self, sem_whatsapp=(), falhar=False):
        self.sem_whatsapp = set(sem_whatsapp)
        self.falhar = falhar
        self.enviados = []
        self.consultas = 0

    def id_whatsapp(self, numero):
        self.consultas += 1
        return None if numero in self.sem_whatsapp else f"{numero}@c.us"

    def enviar_texto(self, chat_id, texto):
        if self.falhar:
            raise ErroWhatsApp("API fora do ar")
        self.enviados.append(("texto", chat_id, texto))

    def enviar_imagem(self, chat_id, jpeg, legenda):
        if self.falhar:
            raise ErroWhatsApp("API fora do ar")
        self.enviados.append(("imagem", chat_id, legenda))

    def conectado(self):
        return True


@pytest.fixture
def cfg():
    c = Config()
    c.modo_teste = False
    c.ddd_padrao, c.pais = "65", "55"
    return c


def test_envia_com_foto_para_cada_contato(cfg):
    banco = BancoFalso([linha(contato_id=1), linha(contato_id=2, telefone="65 3322-1100", nome="Equipe")])
    wa = WhatsAppFalso()
    n = Notificador(banco, wa, cfg, buscar_foto=lambda a: b"\xff\xd8jpeg")
    assert n.ciclo() == 2
    assert [e[0] for e in wa.enviados] == ["imagem", "imagem"]
    assert [r[2] for r in banco.registros] == ["ENVIADO", "ENVIADO"]


def test_sem_foto_envia_so_texto(cfg):
    wa = WhatsAppFalso()
    Notificador(BancoFalso([linha()]), wa, cfg, buscar_foto=lambda a: None).ciclo()
    assert wa.enviados[0][0] == "texto"


def test_numero_invalido_e_sem_whatsapp_sao_registrados_sem_enviar(cfg):
    banco = BancoFalso([linha(contato_id=1, telefone="192"),
                        linha(contato_id=2, telefone="(65) 3322-1100")])
    wa = WhatsAppFalso(sem_whatsapp={"556533221100"})
    assert Notificador(banco, wa, cfg, lambda a: None).ciclo() == 0
    assert [r[2] for r in banco.registros] == ["NUMERO_INVALIDO", "SEM_WHATSAPP"]
    assert wa.enviados == []


def test_falha_da_api_registra_erro_para_nova_tentativa(cfg):
    banco = BancoFalso([linha()])
    Notificador(banco, WhatsAppFalso(falhar=True), cfg, lambda a: None).ciclo()
    assert banco.registros[0][2] == "ERRO"


def test_modo_teste_nao_envia(cfg):
    cfg.modo_teste = True
    banco, wa = BancoFalso([linha()]), WhatsAppFalso()
    Notificador(banco, wa, cfg, lambda a: None).ciclo()
    assert wa.enviados == []
    assert banco.registros[0][2] == "TESTE"


def test_foto_buscada_uma_vez_por_alerta_e_numero_consultado_uma_vez(cfg):
    buscas = []
    banco = BancoFalso([linha(alerta_id=1, contato_id=1), linha(alerta_id=1, contato_id=2, nome="Outro"),
                        linha(alerta_id=2, contato_id=1)])
    wa = WhatsAppFalso()
    Notificador(banco, wa, cfg, lambda a: buscas.append(a["alerta_id"])).ciclo()
    assert buscas == [1, 2]
    assert wa.consultas == 1  # mesmo telefone nas 3 linhas: getNumberId só uma vez


def test_texto_da_mensagem():
    texto = montar_texto({"tipo": "MOVIMENTO_ANOMALO", "camera_nome": "Quarto 2", "camera_local": "1º andar",
                          "ocorrido_em": "2026-11-06T14:32:05"}, {"nome": "Felipe"}, "http://sentinela.local")
    assert "Pessoa no chão" in texto
    assert "Quarto 2 (1º andar)" in texto
    assert "06/11/2026 às 14:32:05" in texto
    assert "Olá, Felipe." in texto
    assert texto.endswith("Painel: http://sentinela.local")


class BancoComContatos(BancoFalso):
    def contatos(self):
        return [{"id": 1, "nome": "Felipe", "telefone": "(65) 99876-5432"},
                {"id": 2, "nome": "Bombeiros", "telefone": "193"}]  # número inválido: ignorado


def test_aviso_de_texto_vai_para_todos_os_contatos_validos(cfg):
    whatsapp = WhatsAppFalso()
    n = Notificador(BancoComContatos([]), whatsapp, cfg, lambda a: None)
    assert n.agendar_aviso("Câmera Quarto 2 sem sinal")
    assert n.enviar_avisos() == 1
    assert whatsapp.enviados == [("texto", "5565998765432@c.us", "Câmera Quarto 2 sem sinal")]
    assert n.enviar_avisos() == 0  # a fila esvaziou


def test_aviso_com_whatsapp_fora_nao_derruba_o_laco(cfg):
    n = Notificador(BancoComContatos([]), WhatsAppFalso(falhar=True), cfg, lambda a: None)
    n.agendar_aviso("x")
    assert n.enviar_avisos() == 0
