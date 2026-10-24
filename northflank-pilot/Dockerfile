FROM node:22-bookworm-slim AS node
FROM python:3.11-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
# The optional CA bundle supports the current build proxy without disabling TLS.
# Northflank builds normally use the image's standard trusted roots.
RUN --mount=type=secret,id=build_ca,mode=0444 \
    build_ca_bundle=/etc/ssl/certs/ca-certificates.crt; \
    if [ -f /run/secrets/build_ca ]; then build_ca_bundle=/run/secrets/build_ca; fi; \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::https::CaInfo="$build_ca_bundle" update -o APT::Update::Error-Mode=any \
    && DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::https::CaInfo="$build_ca_bundle" install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN --mount=type=secret,id=build_ca,mode=0444 \
    build_ca_bundle=/etc/ssl/certs/ca-certificates.crt; \
    if [ -f /run/secrets/build_ca ]; then build_ca_bundle=/run/secrets/build_ca; fi; \
    python -m pip install --cert "$build_ca_bundle" --no-cache-dir -r requirements.txt && python -m pip check
COPY --chown=10001:10001 probe_live.py server.py /app/
RUN useradd --uid 10001 --create-home runner
USER 10001
ENV PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "/app/server.py"]
