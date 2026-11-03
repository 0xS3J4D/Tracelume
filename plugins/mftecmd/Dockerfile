# MFTECmd (MIT, © Eric Zimmerman) built from the pinned source tag on .NET 10.
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
ARG MFTECMD_REF=2026.10.1
RUN git clone --depth 1 --branch ${MFTECMD_REF} https://github.com/EricZimmerman/MFTECmd /src \
 && dotnet publish /src/MFTECmd/MFTECmd.csproj -c Release -f net10.0 -o /out

FROM mcr.microsoft.com/dotnet/runtime:10.0
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /out /opt/mftecmd
COPY _shared/stage.py /opt/stage.py
COPY mftecmd/run_mft.py /opt/run_mft.py
RUN useradd -r -u 10001 tool
USER tool
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1
