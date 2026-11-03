# ALEAPP tool image. ALEAPP is MIT-licensed © Alexis Brignoni and contributors.
FROM python:3.12-slim
ARG ALEAPP_REF=v3.6.0
ENV ALEAPP_REF=${ALEAPP_REF}
RUN python - <<'PY'
import io, tarfile, urllib.request, os
ref = os.environ.get("ALEAPP_REF", "v3.6.0")
url = f"https://codeload.github.com/abrignoni/ALEAPP/tar.gz/refs/tags/{ref}"
data = urllib.request.urlopen(url, timeout=120).read()
with tarfile.open(fileobj=io.BytesIO(data)) as t:
    root = t.getnames()[0].split("/")[0]
    t.extractall("/opt", filter="data")
os.rename(f"/opt/{root}", "/opt/aleapp")
PY
RUN pip install --no-cache-dir -r /opt/aleapp/requirements.txt
RUN useradd -r -u 10001 tool
USER tool
WORKDIR /opt/aleapp
