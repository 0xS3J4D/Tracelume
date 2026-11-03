# MFTECmd (MIT, © Eric Zimmerman) on the .NET 9 runtime.
FROM mcr.microsoft.com/dotnet/runtime:9.0
RUN apt-get update && apt-get install -y --no-install-recommends python3 unzip curl ca-certificates \
 && curl -fsSL -o /tmp/m.zip https://download.ericzimmermanstools.com/net9/MFTECmd.zip \
 && mkdir -p /opt/mftecmd && unzip -q /tmp/m.zip -d /opt/mftecmd && rm /tmp/m.zip \
 && apt-get purge -y curl unzip && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
COPY _shared/stage.py /opt/stage.py
COPY mftecmd/run_mft.py /opt/run_mft.py
RUN useradd -r -u 10001 tool
USER tool
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1
