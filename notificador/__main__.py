"""
Uso:
    python -m notificador              # roda continuamente (Ctrl+C para sair)
    python -m notificador --uma-vez    # processa as pendências atuais e sai
    python -m notificador --status     # confere banco e sessão do WhatsApp
    python -m notificador --teste 65999998888   # envia uma mensagem de teste para esse número
"""

import argparse
import logging
import sys

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    from .banco import Banco
    from .config import Config
    from .servico import Notificador, criar_buscador_de_foto
    from .telefone import normalizar
    from .whatsapp import ClienteWhatsApp, ErroWhatsApp

    parser = argparse.ArgumentParser(prog="notificador", description="Sentinela - alertas por WhatsApp")
    parser.add_argument("--uma-vez", action="store_true", help="processa as pendências e sai")
    parser.add_argument("--status", action="store_true", help="confere banco e WhatsApp e sai")
    parser.add_argument("--teste", metavar="TELEFONE", help="envia uma mensagem de teste e sai")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    cfg = Config()
    whatsapp = ClienteWhatsApp(cfg)

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
            notificador.rodar()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        banco.fechar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
