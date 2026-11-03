# evtx_dump (MIT/Apache-2.0, © Omer Ben-Amram) from crates.io at a pinned version.
FROM rust:1 AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
      clang libclang-dev cmake autoconf automake libtool pkg-config \
 && rm -rf /var/lib/apt/lists/*
RUN cargo install evtx --version 0.15.1 --locked --root /out

FROM python:3.12-slim
COPY --from=build /out/bin/evtx_dump /usr/local/bin/evtx_dump
COPY _shared/stage.py /opt/stage.py
COPY evtx/run_evtx.py /opt/run_evtx.py
RUN useradd -r -u 10001 tool
USER tool
