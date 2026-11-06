# Sentinela — Notificações por WhatsApp

Serviço que envia os alertas de queda do **Sentinela** por WhatsApp para os **contatos de emergência**
cadastrados na tela de Configurações. Lê o mesmo PostgreSQL do Sentinela e envia pela API
[whatsapp-api](https://github.com/chrishubert/whatsapp-api) (whatsapp-web.js).

```
Sentinela (DetectHumans) ──grava──▶ PostgreSQL ◀──lê/registra── Notificador (este repo) ──▶ whatsapp-api ──▶ WhatsApp
```

## Como funciona

A cada 3 s o notificador:
1. busca alertas **PENDENTES** dos últimos 10 min × cada contato de emergência ainda não notificado;
2. normaliza o telefone (`(65) 99876-5432` → `5565998765432`) e pergunta à API o ID real no
   WhatsApp (`getNumberId`), o que resolve números cadastrados com ou sem o 9º dígito;
3. envia a **foto do momento com a mensagem** (ou só texto, se a foto não estiver disponível):

   > 🚨 **SENTINELA — Queda detectada**
   > Olá, Felipe.
   > 📍 **Local:** Quarto 2 (1º andar)
   > 🕒 **Horário:** 06/11/2026 às 14:32:05
   > Verifique o residente imediatamente.

4. registra o resultado em `notificacao_whatsapp` (tabela criada automaticamente).

| Status | Significado | Tenta de novo? |
|---|---|---|
| `ENVIADO` | entregue à API do WhatsApp | — |
| `ERRO` | API/rede falhou | sim, até 3 vezes |
| `SEM_WHATSAPP` | número não tem WhatsApp | não |
| `NUMERO_INVALIDO` | ex.: `192` | não |
| `TESTE` | modo teste: nada foi enviado | não |

Regras importantes:
- cada contato recebe **no máximo uma mensagem por alerta** (`UNIQUE(alerta_id, contato_id)`), mesmo reiniciando o serviço;
- alerta resolvido no painel antes do envio **não** é enviado;
- ao ligar o serviço, alertas com mais de 10 min são ignorados (não dispara mensagens antigas).

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # preencha banco e WHATSAPP_API_KEY
```

## 1. Subir a API do WhatsApp

Em `C:\whatsapp-api` (clone do chrishubert/whatsapp-api):

```powershell
npm install
npm start                   # http://localhost:3000
```

Na primeira vez (ou quando `--status` mostrar "NÃO conectado"), conecte o WhatsApp que vai **enviar** os alertas:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\parear_whatsapp.ps1
```

O QR Code abre na tela; leia no celular em **WhatsApp → Aparelhos conectados → Conectar um aparelho**.

> Se a whatsapp-api cair ao iniciar com `onQRChangedEvent already exists` ou `Execution context was destroyed`,
> a sessão/cache salvos ficaram velhos: renomeie a pasta `.wwebjs_cache` da whatsapp-api e rode o pareamento de novo.

A documentação das rotas fica em `http://localhost:3000/api-docs` (se `ENABLE_SWAGGER_ENDPOINT=TRUE`).

## 2. Rodar o notificador

```powershell
python -m notificador --status            # confere banco e sessão do WhatsApp
python -m notificador --teste 65999998888 # manda uma mensagem de teste para esse número
python -m notificador                     # roda continuamente (Ctrl+C para sair)
python -m notificador --uma-vez           # processa as pendências e sai
```

Para validar sem mandar mensagens: `NOTIF_MODO_TESTE=true` no `.env`.

> No Sentinela (DetectHumans), deixe `WHATSAPP_URL` **vazio** no `.env` para não enviar duas vezes
> (o envio antigo mandava só para um número fixo).

## Testes

```powershell
python -m pytest -v
```

Sem rede e sem banco: telefone, texto da mensagem e o laço com banco/WhatsApp falsos
(envio com/sem foto, número inválido, sem WhatsApp, falha da API, modo teste, cache de números).

## Segurança e LGPD

- `.env` (senha do banco e chave da API) fica fora do git.
- A API do WhatsApp deve ficar acessível só na rede interna e sempre com `API_KEY`.
- A mensagem traz só local, horário e a foto do momento; nenhum vídeo é enviado.
- A conta de WhatsApp usada deve ser da instituição, não pessoal (whatsapp-web.js não é API oficial;
  para produção em escala, avaliar a WhatsApp Business Cloud API).
