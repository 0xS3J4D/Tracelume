# iLEAPP tool image. iLEAPP is MIT-licensed © Alexis Brignoni and contributors.
FROM python:3.12-slim
ARG iLEAPP_REF=v2026.4.6
ENV iLEAPP_REF=${iLEAPP_REF}
RUN python - <<'PY'
import io, tarfile, urllib.request, os
ref = os.environ.get("iLEAPP_REF", "v2026.4.6")
url = f"https://codeload.github.com/abrignoni/iLEAPP/tar.gz/refs/tags/{ref}"
data = urllib.request.urlopen(url, timeout=120).read()
with tarfile.open(fileobj=io.BytesIO(data)) as t:
    root = t.getnames()[0].split("/")[0]
    t.extractall("/opt", filter="data")
os.rename(f"/opt/{root}", "/opt/ileapp")
PY
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
 && pip install --no-cache-dir -r /opt/ileapp/requirements.txt \
 && apt-get purge -y build-essential && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
RUN useradd -r -u 10001 tool
USER tool
WORKDIR /opt/ileapp
