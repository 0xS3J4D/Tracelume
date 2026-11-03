# Media scanner: ExifTool (© Phil Harvey, Artistic/GPL) + Pillow for thumbnails.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libimage-exiftool-perl \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "pillow==11.*" "pillow-heif==1.*"
COPY media_scan.py /opt/media_scan.py
RUN useradd -r -u 10001 tool
USER tool
