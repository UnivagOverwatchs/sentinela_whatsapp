# Sentinela — Notificações por WhatsApp

Serviço que envia os alertas de queda do **Sentinela** por WhatsApp para os **contatos de emergência**
cadastrados na tela de Configurações. Lê o mesmo PostgreSQL do Sentinela e envia pela API
[whatsapp-api](https://github.com/chrishubert/whatsapp-api) (whatsapp-web.js).

```
Servidor A: Sentinela (DetectHumans) ──grava──▶ PostgreSQL ◀──lê/registra──┐
                     │                                                    │
                     └── POST /notificar (token) ──▶ Servidor B: Notificador (este repo) ──▶ whatsapp-api ──▶ WhatsApp
```

O aviso `POST /notificar` faz o envio sair **na hora**; se ele falhar (rede), o notificador encontra
o alerta sozinho na verificação do banco a cada 3 s.

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

## Subir no servidor com Docker (recomendado)

No servidor (Linux com Docker e Docker Compose):

```bash
git clone https://github.com/UnivagOverwatchs/sentinela_whatsapp.git
cd sentinela_whatsapp
cp .env.example .env        # preencha: PG* (banco), WHATSAPP_API_KEY, NOTIF_TOKEN, SENTINELA_API_URL
docker compose up -d --build
docker compose run --rm notificador --parear   # 1ª vez: QR Code no terminal, leia no celular
docker compose ps                              # os dois serviços devem ficar "healthy"
curl http://localhost:8100/saude               # {"whatsapp_conectado": true, ...}
```

| Serviço | Imagem | Porta |
|---|---|---|
| `whatsapp-api` | `gateway/Dockerfile`: whatsapp-api + whatsapp-web.js 1.34.7 + correções, usuário sem root | interna (não exposta) |
| `notificador` | `Dockerfile`: Python 3.12 slim, usuário sem root | `8100` (`/notificar`, `/saude`) |

- A sessão do WhatsApp fica no volume `whatsapp_sessoes` (sobrevive a reinícios e atualizações).
- Gere o token com `python -c "import secrets; print(secrets.token_urlsafe(32))"` e use o **mesmo valor**
  em `NOTIF_TOKEN` (aqui) e `NOTIFICADOR_TOKEN` (Sentinela).
- Libere a porta 8100 no firewall **só para o IP do servidor do Sentinela**.
- Atualizar: `git pull && docker compose up -d --build`. Logs: `docker compose logs -f notificador`.

### Ligando o Sentinela

No `.env` do Sentinela (DetectHumans):

```env
NOTIFICADOR_URL=http://IP-DO-SERVIDOR-B:8100
NOTIFICADOR_TOKEN=<mesmo valor de NOTIF_TOKEN>
# WHATSAPP_URL=   (deixe vazio: era o envio antigo para um número fixo)
```

Ao iniciar, o Sentinela mostra `WhatsApp: avisando o notificador em http://...`.

## Rodar sem Docker (desenvolvimento)

### Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # preencha banco e WHATSAPP_API_KEY
```

### 1. Subir a API do WhatsApp

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

### 2. Rodar o notificador

```powershell
python -m notificador --status            # confere banco e sessão do WhatsApp
python -m notificador --teste 65999998888 # manda uma mensagem de teste para esse número
python -m notificador                     # roda continuamente (Ctrl+C para sair)
python -m notificador --uma-vez           # processa as pendências e sai
python -m notificador --parear            # QR Code no terminal (alternativa ao script .ps1)
```

Para validar sem mandar mensagens: `NOTIF_MODO_TESTE=true` no `.env`.

> No Sentinela (DetectHumans), deixe `WHATSAPP_URL` **vazio** no `.env` para não enviar duas vezes
> (o envio antigo mandava só para um número fixo).

## Testes

```powershell
python -m pytest -v
```

23 testes, sem rede externa e sem banco: telefone, texto da mensagem, leitura do `.env`
(comentário no fim da linha), laço com banco/WhatsApp falsos (envio com/sem foto, número inválido,
sem WhatsApp, falha da API, modo teste, cache de números) e a API HTTP (token, `/notificar`, `/saude`).

## Segurança e LGPD

- `.env` (senha do banco, chave da API e token) fica fora do git e fora da imagem Docker (`.dockerignore`).
- `POST /notificar` exige token (comparação em tempo constante); sem `NOTIF_TOKEN` a rota fica desligada.
- A API do WhatsApp deve ficar acessível só na rede interna e sempre com `API_KEY`.
- A mensagem traz só local, horário e a foto do momento; nenhum vídeo é enviado.
- A conta de WhatsApp usada deve ser da instituição, não pessoal (whatsapp-web.js não é API oficial;
  para produção em escala, avaliar a WhatsApp Business Cloud API).
