"""
notificador - Envia os alertas do Sentinela por WhatsApp para os contatos de emergência.

LÓGICA GERAL
------------
    Sentinela (detecção) ──grava──▶ PostgreSQL: alerta + evento + contato_emergencia
                                            │
                     a cada 3 s ◀──lê───────┘
    Notificador (este serviço)
        1. busca alertas PENDENTES recentes que ainda não foram enviados a cada contato;
        2. normaliza o telefone e pergunta à API do WhatsApp o ID real do número
           (resolve o 9º dígito dos celulares brasileiros);
        3. envia a mensagem com a foto do momento (ou só texto, se a foto não estiver disponível);
        4. registra o resultado em `notificacao_whatsapp` (não repete envios; tenta de novo em caso de erro).

    WhatsApp: API REST "whatsapp-api" (whatsapp-web.js), rodando em outro processo/máquina.

Módulos:
    config.py    -> variáveis de ambiente (.env)
    telefone.py  -> normalização de números brasileiros
    mensagem.py  -> texto enviado
    banco.py     -> consultas no PostgreSQL do Sentinela + tabela de controle
    whatsapp.py  -> cliente da API whatsapp-api
    servico.py   -> laço principal (o que enviar, para quem, e como registrar)
"""
