# syntax=docker/dockerfile:1
#
# Imagem do notificador (Python). Duas etapas:
#   build   -> instala as dependências num ambiente virtual (/opt/venv);
#   runtime -> copia só o ambiente pronto + o código, sem ferramentas de build, usuário sem root.

FROM python:3.12-slim AS build
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# requirements montado (não copiado) e cache do pip fora da imagem final.
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    pip install -r requirements.txt

FROM python:3.12-slim AS runtime
LABEL org.opencontainers.image.source="https://github.com/UnivagOverwatchs/sentinela_whatsapp" \
      org.opencontainers.image.description="Sentinela - notificações de queda por WhatsApp"
RUN groupadd --system --gid 1001 app && useradd --system --uid 1001 --gid app --no-create-home app
WORKDIR /app
COPY --link --from=build /opt/venv /opt/venv
COPY --link --chown=1001:1001 notificador/ notificador/
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=America/Cuiaba
USER app
EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/saude', timeout=4).status == 200 else 1)"
ENTRYPOINT ["python", "-m", "notificador"]
