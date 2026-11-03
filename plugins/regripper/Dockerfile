# RegRipper 3.0 (MIT, © Harlan Carvey) from the Debian package, with Perl dependencies.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends regripper \
 && rm -rf /var/lib/apt/lists/*
COPY _shared/stage.py /opt/stage.py
COPY regripper/run_rr.py /opt/run_rr.py
RUN useradd -r -u 10001 tool
USER tool
