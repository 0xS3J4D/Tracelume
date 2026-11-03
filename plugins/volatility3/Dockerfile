# Volatility 3 tool image. Volatility 3 is under the Volatility Software License
# © the Volatility Foundation. Symbol packs are bundled so analysis runs fully offline.
FROM python:3.12-slim
RUN pip install --no-cache-dir "volatility3[full]==2.28.2"
RUN python - <<'PY'
import os, urllib.request, site
dest = os.path.join(site.getsitepackages()[0], "volatility3", "symbols")
for name in ("windows.zip", "linux.zip", "mac.zip"):
    url = f"https://downloads.volatilityfoundation.org/volatility3/symbols/{name}"
    print("fetching", url, flush=True)
    urllib.request.urlretrieve(url, os.path.join(dest, name))
PY
COPY run_vol.py /opt/run_vol.py
RUN useradd -r -u 10001 tool && mkdir -p /home/tool/.cache && chown -R tool /home/tool
USER tool
ENV HOME=/home/tool
