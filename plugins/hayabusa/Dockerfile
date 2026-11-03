# Hayabusa (AGPL-3.0, © Yamato Security) built from the pinned source tag, with its Sigma-based
# rule set bundled at build time so it runs with no network.
FROM rust:1 AS build
ARG HAYABUSA_REF=v4.3.1
RUN git clone --depth 1 --branch ${HAYABUSA_REF} https://github.com/Yamato-Security/hayabusa /src \
 && git clone --depth 1 https://github.com/Yamato-Security/hayabusa-rules /src/rules \
 && cd /src && cargo build --release --locked

FROM python:3.12-slim
COPY --from=build /src/target/release/hayabusa /opt/hayabusa/hayabusa
COPY --from=build /src/rules /opt/hayabusa/rules
COPY --from=build /src/config /opt/hayabusa/config
COPY _shared/stage.py /opt/stage.py
COPY hayabusa/run.sh /opt/run.sh
RUN useradd -r -u 10001 tool && chown -R tool /opt/hayabusa
USER tool
WORKDIR /opt/hayabusa
