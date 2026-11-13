"""
servico.py - Laço principal: decide o que enviar, para quem, e registra o resultado.

Recebe banco, cliente do WhatsApp e a função que busca a foto por parâmetro
(injeção de dependência): nos testes usamos versões falsas, sem rede.
"""

import logging
import os
import queue
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional

import requests

from .config import Config
from .mensagem import montar_texto
from .telefone import normalizar
from .whatsapp import ErroWhatsApp

log = logging.getLogger("notificador")


def criar_buscador_de_foto(cfg: Config) -> Callable[[Dict[str, Any]], Optional[bytes]]:
    """
    Foto do alerta: 1º tenta a API do Sentinela (/api/alertas/{id}/imagem);
    se não der, lê o arquivo direto da pasta do DetectHumans (SENTINELA_PASTA). Sem foto -> None.
    """
    def buscar(alerta: Dict[str, Any]) -> Optional[bytes]:
        try:
            r = requests.get(f"{cfg.sentinela_api_url}/api/alertas/{alerta['alerta_id']}/imagem", timeout=5)
            if r.ok and r.headers.get("content-type", "").startswith("image/"):
                return r.content
        except requests.RequestException:
            pass
        if cfg.sentinela_pasta and alerta.get("imagem"):
            caminho = os.path.join(cfg.sentinela_pasta, alerta["imagem"])
            if os.path.isfile(caminho):
                with open(caminho, "rb") as arquivo:
                    return arquivo.read()
        return None
    return buscar


class Notificador:
    def __init__(self, banco, whatsapp, cfg: Config, buscar_foto: Callable[[Dict[str, Any]], Optional[bytes]]):
        self.banco = banco
        self.whatsapp = whatsapp
        self.cfg = cfg
        self.buscar_foto = buscar_foto
        self._ids: Dict[str, Optional[str]] = {}  # cache número -> ID do WhatsApp
        # POST /notificar seta este evento: o laço acorda na hora, sem esperar o intervalo.
        self.acordar = threading.Event()
        # Resumo do último ciclo, lido pelo GET /saude (o banco só é usado pela thread do laço).
        self.ultimo_ciclo = {"ok": None, "em": None, "enviados": 0, "erro": None}
        # Avisos de texto (POST /aviso, ex.: "câmera sem sinal"). Quem envia é o laço, como os alertas.
        # Fila limitada: se o WhatsApp estiver fora e chegarem muitos avisos, os excedentes são descartados.
        self._avisos: "queue.Queue[str]" = queue.Queue(maxsize=50)

    # ------------------------------------------------------------ avisos de texto
    def agendar_aviso(self, texto: str) -> bool:
        """Chamado pela API HTTP. Devolve False se a fila estiver cheia."""
        try:
            self._avisos.put_nowait(texto)
        except queue.Full:
            return False
        self.acordar.set()
        return True

    def enviar_avisos(self) -> int:
        """Envia os avisos da fila a TODOS os contatos. Sem registro no banco nem nova tentativa:
        um aviso de câmera perdido é menos grave que repetir mensagens; o painel também avisa por push."""
        enviados = 0
        while True:
            try:
                texto = self._avisos.get_nowait()
            except queue.Empty:
                return enviados
            for contato in self.banco.contatos():
                enviados += self._avisar_contato(contato, texto)

    def _avisar_contato(self, contato: Dict[str, Any], texto: str) -> int:
        rotulo = f"aviso -> {contato['nome']}"
        numero = normalizar(contato["telefone"], self.cfg.ddd_padrao, self.cfg.pais)
        if not numero:
            return 0
        try:
            if numero not in self._ids:
                self._ids[numero] = self.whatsapp.id_whatsapp(numero)
            chat_id = self._ids[numero]
            if not chat_id:
                return 0
            if self.cfg.modo_teste:
                log.info("%s: [MODO TESTE] não enviado", rotulo)
                return 0
            self.whatsapp.enviar_texto(chat_id, texto)
            log.info("%s: enviado", rotulo)
            return 1
        except ErroWhatsApp as erro:
            log.warning("%s: falhou: %s", rotulo, erro)
            return 0

    # ------------------------------------------------------------ um ciclo
    def ciclo(self) -> int:
        """Processa as pendências atuais. Devolve quantas mensagens foram enviadas."""
        pendencias = self.banco.pendencias(self.cfg.janela_min, self.cfg.max_tentativas)
        enviados = 0
        for alerta_id, linhas in self._agrupar_por_alerta(pendencias).items():
            foto = self.buscar_foto(linhas[0])  # uma busca por alerta, não por contato
            for linha in linhas:
                enviados += self._notificar_contato(linha, foto)
        return enviados

    @staticmethod
    def _agrupar_por_alerta(pendencias: List[Dict[str, Any]]) -> "OrderedDict[int, List[Dict[str, Any]]]":
        grupos: "OrderedDict[int, List[Dict[str, Any]]]" = OrderedDict()
        for linha in pendencias:
            grupos.setdefault(linha["alerta_id"], []).append(linha)
        return grupos

    def _notificar_contato(self, linha: Dict[str, Any], foto: Optional[bytes]) -> int:
        alerta_id, contato_id = linha["alerta_id"], linha["contato_id"]
        rotulo = f"alerta {alerta_id} -> {linha['contato_nome']}"

        numero = normalizar(linha["telefone"], self.cfg.ddd_padrao, self.cfg.pais)
        if not numero:
            log.info("%s: telefone inválido para WhatsApp, ignorado", rotulo)
            self.banco.registrar(alerta_id, contato_id, "NUMERO_INVALIDO")
            return 0

        try:
            if numero not in self._ids:
                self._ids[numero] = self.whatsapp.id_whatsapp(numero)
            chat_id = self._ids[numero]
            if not chat_id:
                log.info("%s: número sem WhatsApp", rotulo)
                self.banco.registrar(alerta_id, contato_id, "SEM_WHATSAPP")
                return 0

            texto = montar_texto(
                {"tipo": linha["tipo"], "camera_nome": linha["camera_nome"],
                 "camera_local": linha["camera_local"], "ocorrido_em": linha["ocorrido_em"]},
                {"nome": linha["contato_nome"]}, self.cfg.painel_url)

            if self.cfg.modo_teste:
                log.info("%s: [MODO TESTE] mensagem NÃO enviada para %s", rotulo, chat_id)
                self.banco.registrar(alerta_id, contato_id, "TESTE", chat_id)
                return 0

            if foto:
                self.whatsapp.enviar_imagem(chat_id, foto, texto)
            else:
                self.whatsapp.enviar_texto(chat_id, texto)
            log.info("%s: enviado (%s)", rotulo, "com foto" if foto else "só texto")
            self.banco.registrar(alerta_id, contato_id, "ENVIADO", chat_id)
            return 1
        except ErroWhatsApp as erro:
            log.warning("%s: falhou (tentativa %d): %s", rotulo, linha["tentativas"] + 1, erro)
            self.banco.registrar(alerta_id, contato_id, "ERRO", self._ids.get(numero), str(erro))
            return 0

    # ------------------------------------------------------------ laço contínuo
    def rodar(self) -> None:
        log.info("Notificador iniciado (a cada %ss, alertas dos últimos %s min%s).",
                 self.cfg.intervalo_s, self.cfg.janela_min, ", MODO TESTE" if self.cfg.modo_teste else "")
        if not self.whatsapp.conectado():
            log.warning("Sessão '%s' do WhatsApp não está conectada em %s. Os envios vão falhar "
                        "até ler o QR Code (ver README).", self.cfg.sessao, self.cfg.whatsapp_url)
        espera = self.cfg.intervalo_s
        while True:
            self.acordar.clear()
            try:
                enviados = self.ciclo() + self.enviar_avisos()
                self.ultimo_ciclo = {"ok": True, "em": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                     "enviados": enviados, "erro": None}
                espera = self.cfg.intervalo_s
            except Exception as erro:  # noqa: BLE001 - banco fora do ar etc.: registra e tenta de novo depois
                log.exception("Erro no ciclo; nova tentativa em %ss", espera)
                self.ultimo_ciclo = {"ok": False, "em": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                     "enviados": 0, "erro": str(erro)[:200]}
                espera = min(espera * 2, 60)
            # Dorme até o próximo ciclo OU até o Sentinela chamar POST /notificar.
            self.acordar.wait(timeout=espera)
