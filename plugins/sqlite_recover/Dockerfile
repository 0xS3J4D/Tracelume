# Tracelume SQLite carver: pure Python standard library, no third-party code.
FROM python:3.12-slim
COPY sqlite_carve.py /opt/sqlite_carve.py
RUN useradd -r -u 10001 tool
USER tool
