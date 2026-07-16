# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE}

ARG APP_VERSION=0.4.0
LABEL org.opencontainers.image.title="Agent Anthill" \
    org.opencontainers.image.description="Evidence-linked runtime observability for agent systems" \
    org.opencontainers.image.version="${APP_VERSION}" \
    org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    ANTHILL_DATA_DIR=/app/.anthill-data

ARG APP_UID=10001
ARG APP_GID=10001

RUN groupadd --gid "${APP_GID}" anthill \
    && useradd \
        --uid "${APP_UID}" \
        --gid "${APP_GID}" \
        --no-create-home \
        --shell /usr/sbin/nologin \
        anthill

WORKDIR /app

COPY --chown=0:0 requirements.txt ./
RUN python -m pip install --no-cache-dir --requirement requirements.txt

COPY --chown=0:0 server.py ./
COPY --chown=0:0 analyzer ./analyzer
COPY --chown=0:0 anthill ./anthill
COPY --chown=0:0 tracer ./tracer
COPY --chown=0:0 static ./static
COPY --chown=0:0 samples ./samples
COPY --chown=0:0 LICENSE NOTICE ./

RUN mkdir -p "${ANTHILL_DATA_DIR}" \
    && chown "${APP_UID}:${APP_GID}" "${ANTHILL_DATA_DIR}" \
    && chmod 0700 "${ANTHILL_DATA_DIR}"

VOLUME ["/app/.anthill-data"]

USER ${APP_UID}:${APP_GID}

EXPOSE 8765
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/anthill/schema', timeout=3).close()"]

ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["server:app", "--host", "0.0.0.0", "--port", "8765"]
