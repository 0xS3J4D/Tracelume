# Chainsaw (GPL-3.0, © WithSecure Labs) built from the pinned tag; its detection rules are bundled.
FROM rust:1 AS build
ARG CHAINSAW_REF=v2.17.1
RUN git clone --depth 1 --branch ${CHAINSAW_REF} https://github.com/WithSecureLabs/chainsaw /src \
 && cd /src && cargo build --release --locked

FROM python:3.12-slim
COPY --from=build /src/target/release/chainsaw /opt/chainsaw/chainsaw
COPY --from=build /src/rules /opt/chainsaw/rules
COPY _shared/stage.py /opt/stage.py
RUN useradd -r -u 10001 tool
USER tool
