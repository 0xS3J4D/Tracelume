# Mobile Verification Toolkit (MVT License 1.1, © Amnesty International Security Lab).
# Public indicators of compromise are downloaded at build time so checks run offline.
FROM python:3.12-slim
RUN pip install --no-cache-dir "mvt==2026.11.2"
RUN useradd -r -u 10001 -m tool
USER tool
RUN mvt-ios download-iocs
COPY _shared/stage.py /opt/stage.py
COPY mvt/run_mvt.sh /opt/run_mvt.sh
