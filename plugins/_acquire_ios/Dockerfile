# iPhone logical backup over USB: usbmuxd + libimobiledevice (LGPL-2.1, © libimobiledevice
# contributors). Linux hosts only (USB passthrough). The phone must be unlocked and trusted.
FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      usbmuxd libimobiledevice-utils python3 ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY acquire.py /opt/acquire.py
ENTRYPOINT []
