# Tracelume launcher for Windows (PowerShell). Requires Docker Desktop.
#   powershell -ExecutionPolicy Bypass -File .\tracelume.ps1 start
param([string]$Command = "start", [string]$Arg = "")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Port = if ($env:TRACELUME_PORT) { $env:TRACELUME_PORT } else { "8080" }
$Url = "http://127.0.0.1:$Port"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Write-Error "Install Docker Desktop first: https://www.docker.com/products/docker-desktop/"; exit 1 }
docker info *> $null; if ($LASTEXITCODE -ne 0) { Write-Error "Docker Desktop is not running. Start it and try again."; exit 1 }

function Get-Images([string[]]$Extra) {
  docker compose @Extra pull --quiet --ignore-pull-failures
  docker compose @Extra up --no-start --no-build *> $null
  if ($LASTEXITCODE -ne 0) { docker compose @Extra up --no-start }
}

switch ($Command) {
  "start" {
    Get-Images @()
    docker compose up -d
    Write-Host -NoNewline "Waiting for Tracelume"
    for ($i = 0; $i -lt 60; $i++) {
      try { Invoke-WebRequest "$Url/api/health" -UseBasicParsing -TimeoutSec 2 | Out-Null; break } catch { Write-Host -NoNewline "."; Start-Sleep 1 }
    }
    Write-Host "`nTracelume is running at $Url (only reachable from this computer)."
    Start-Process $Url
  }
  "stop"   { docker compose down }
  "status" { docker compose ps }
  "logs"   { docker compose logs -f --tail=100 }
  "tools"  { Get-Images @("--profile", "tools"); docker compose --profile tools rm -f *> $null; Write-Host "Tool images ready." }
  "build"  { docker compose --profile tools build }
  "update" { git pull --ff-only; & $PSCommandPath tools; docker compose up -d }
  "ai" {
    $model = if ($Arg) { $Arg } else { "qwen2.5:7b-instruct" }
    docker run --rm -v tracelume_ollama:/root/.ollama --entrypoint sh ollama/ollama:0.40.13 -c "ollama serve >/dev/null 2>&1 & sleep 3; ollama pull '$model'"
    docker compose --profile ai up -d ollama
    Write-Host "Local model ready. In Tracelume -> Settings, set the model to: $model"
  }
  "backup" {
    New-Item -ItemType Directory -Force backups | Out-Null
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    docker compose exec -T db pg_dump -U tracelume -Fc tracelume -f "/tmp/db.dump"
    docker compose cp "db:/tmp/db.dump" "backups/db-$stamp.dump"
    docker run --rm -v tracelume_evidence:/e:ro -v tracelume_workspace:/w:ro -v "${PWD}/backups:/b" alpine:3.20 tar czf "/b/data-$stamp.tgz" -C / e w
    Get-FileHash "backups/db-$stamp.dump", "backups/data-$stamp.tgz" -Algorithm SHA256 | Format-Table -AutoSize | Out-File "backups/SHA256SUMS-$stamp.txt"
    Write-Host "Backup written to backups\"
  }
  default { Write-Host "usage: .\tracelume.ps1 start|stop|status|logs|tools|ai [model]|backup|update|build"; exit 2 }
}
