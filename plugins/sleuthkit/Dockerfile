# The Sleuth Kit tool image (Debian package). TSK © Brian Carrier and contributors.
# Supports raw/dd, E01 (libewf) and AFF images.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends sleuthkit \
 && rm -rf /var/lib/apt/lists/*
COPY tsk_run.py /opt/tsk_run.py
RUN useradd -r -u 10001 tool
USER tool
