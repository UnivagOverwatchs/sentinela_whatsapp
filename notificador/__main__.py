"""
Uso:
    python -m notificador              # roda continuamente (Ctrl+C para sair)
    python -m notificador --uma-vez    # processa as pendências atuais e sai
    python -m notificador --status     # confere banco e sessão do WhatsApp
    python -m notificador --teste 65999998888   # envia uma mensagem de teste para esse número
    python -m notificador --parear     # mostra o QR Code no terminal para conectar o WhatsApp (servidor sem tela)
"""

import argparse
import logging
import sys
import time


def parear(whatsapp, tempo_max_s: int = 180) -> int:
    """Reinicia a sessão e desenha o QR Code no terminal até o celular ler (ou o tempo acabar)."""
    import qrcode

    whatsapp.encerrar_sessao()
    time.sleep(3)
    whatsapp.iniciar_sessao()
    ultimo = None
    limite = time.time() + tempo_max_s
    while time.time() < limite:
        if whatsapp.conectado():
            print("\nWhatsApp CONECTADO.")
            return 0
        atual = whatsapp.qr()
        if atual and atual != ultimo:
            ultimo = atual
            qr = qrcode.QRCode(border=1)
            qr.add_data(atual)
            print("\nLeia no celular: WhatsApp > Aparelhos conectados > Conectar um aparelho\n")
            qr.print_ascii(invert=True)
        time.sleep(3)
    print("Tempo esgotado. Rode --parear de novo.")
    return 1

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    from .banco import Banco
    from .config import Config
    from .http_api import iniciar_em_segundo_plano
    from .servico import Notificador, criar_buscador_de_foto
    from .telefone import normalizar
    from .whatsapp import ClienteWhatsApp, ErroWhatsApp

    parser = argparse.ArgumentParser(prog="notificador", description="Sentinela - alertas por WhatsApp")
    parser.add_argument("--uma-vez", action="store_true", help="processa as pendências e sai")
    parser.add_argument("--status", action="store_true", help="confere banco e WhatsApp e sai")
    parser.add_argument("--teste", metavar="TELEFONE", help="envia uma mensagem de teste e sai")
    parser.add_argument("--parear", action="store_true", help="mostra o QR Code para conectar o WhatsApp")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    cfg = Config()
    whatsapp = ClienteWhatsApp(cfg)

    if args.parear:
        return parear(whatsapp)

    if args.teste:
        numero = normalizar(args.teste, cfg.ddd_padrao, cfg.pais)
        if not numero:
            print("Telefone inválido.")
            return 1
        try:
            chat_id = whatsapp.id_whatsapp(numero)
            if not chat_id:
                print(f"{numero} não tem WhatsApp.")
                return 1
            whatsapp.enviar_texto(chat_id, "✅ Teste do Sentinela: as notificações de queda chegarão por aqui.")
            print(f"Mensagem de teste enviada para {chat_id}.")
            return 0
        except ErroWhatsApp as erro:
            print(f"Falha: {erro}")
            return 1

    banco = Banco()
    print(f"Banco: {banco.descricao}")
    print(f"WhatsApp: {cfg.whatsapp_url} sessão '{cfg.sessao}' -> "
          f"{'conectado' if whatsapp.conectado() else 'NÃO conectado'}")
    if args.status:
        return 0

    notificador = Notificador(banco, whatsapp, cfg, criar_buscador_de_foto(cfg))
    try:
        if args.uma_vez:
            print(f"Mensagens enviadas: {notificador.ciclo()}")
        else:
            iniciar_em_segundo_plano(notificador, cfg.http_porta)
            notificador.rodar()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        banco.fechar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
