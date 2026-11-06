# syntax=docker/dockerfile:1
#
# Imagem da whatsapp-api (github.com/chrishubert/whatsapp-api, licença MIT) com as correções
# que fizeram o envio funcionar no ambiente da equipe:
#   1. whatsapp-web.js 1.34.7 (a imagem pública é de 2024 e vem com a 1.26.0, que não abre
#      mais o WhatsApp Web atual: "onQRChangedEvent already exists");
#   2. clientController.js com os ajustes de compatibilidade (markedUnread / getMaybeMeUser);
#   3. roda como usuário sem privilégios (node), não como root.

# Base fixada por digest: o mesmo build sempre produz a mesma imagem.
FROM chrishubert/whatsapp-web-api@sha256:e929c16a970f60350b4974d68a08c5a8cea59124ff97741de2001628b9cc1392

WORKDIR /usr/src/app

# Atualiza só a biblioteca do WhatsApp; --ignore-scripts + PUPPETEER_SKIP_CHROMIUM_DOWNLOAD
# (já definido na base) evitam baixar outro Chromium: usa o do Alpine.
RUN --mount=type=cache,target=/root/.npm \
    npm install --omit=dev --no-save --ignore-scripts whatsapp-web.js@1.34.7

COPY --chown=node:node clientController.js src/controllers/clientController.js

# Pastas onde a API grava (sessão do WhatsApp e cache da versão do WhatsApp Web).
RUN mkdir -p sessions .wwebjs_cache && chown node:node sessions .wwebjs_cache

USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD wget -qO- http://127.0.0.1:3000/ping || exit 1
CMD ["node", "server.js"]
