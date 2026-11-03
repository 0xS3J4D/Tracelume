# Tool image for MyTool (<licence>, © <authors>). Pin an exact version.
FROM python:3.12-slim
RUN pip install --no-cache-dir mytool==1.2.3
RUN useradd -r -u 10001 tool
USER tool
