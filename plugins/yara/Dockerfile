# YARA (BSD-3-Clause, © VirusTotal) from the Debian package.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends yara \
 && rm -rf /var/lib/apt/lists/*
COPY _shared/stage.py /opt/stage.py
COPY yara/run_yara.py /opt/run_yara.py
RUN useradd -r -u 10001 tool
USER tool
