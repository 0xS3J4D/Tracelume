# ALEAPP tool image. ALEAPP is MIT-licensed © Alexis Brignoni and contributors.
FROM python:3.12-slim
ARG ALEAPP_REF=v3.6.0
RUN apt-get update && apt-get install -y --no-install-recommends git \
 && git clone --depth 1 --branch ${ALEAPP_REF} https://github.com/abrignoni/ALEAPP /opt/aleapp \
 && pip install --no-cache-dir -r /opt/aleapp/requirements.txt \
 && apt-get purge -y git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* /opt/aleapp/.git
RUN useradd -r -u 10001 tool
USER tool
WORKDIR /opt/aleapp
