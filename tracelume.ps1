# Tracelume launcher for Windows (PowerShell). Requires Docker Desktop.
#   powershell -ExecutionPolicy Bypass -File .\tracelume.ps1 start
param([string]$Command = "start", [string]$Arg = "")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Port = if ($env:TRACELUME_PORT) { $env:TRACELUME_PORT } else { "8080" }
$Url = "http://127.0.0.1:$Port"
New-Item -ItemType Directory -Force import, backups | Out-Null
if (-not (Test-Path import\synthetic-android.zip)) { Copy-Item demo\synthetic-android.zip import\ -ErrorAction SilentlyContinue }

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
  "backup" { docker compose exec -T api python -m tracelume.backup create; Write-Host "Backup written to .\backups" }
  "restore" {
    if (-not (Test-Path $Arg)) { Write-Error "usage: .\tracelume.ps1 restore backups\<file>.tar.gz"; exit 1 }
    $ok = Read-Host "This REPLACES all current data. Type RESTORE to continue"
    if ($ok -ne "RESTORE") { exit 1 }
    docker compose down
    docker volume rm tracelume_db tracelume_evidence tracelume_workspace *> $null
    docker compose up -d db redis
    Copy-Item $Arg backups\ -ErrorAction SilentlyContinue
    if (Test-Path "$Arg.sha256") { Copy-Item "$Arg.sha256" backups\ -ErrorAction SilentlyContinue }
    docker compose run --rm api python -m tracelume.backup restore "/backups/$(Split-Path $Arg -Leaf)"
    docker compose up -d
  }
  default { Write-Host "usage: .\tracelume.ps1 start|stop|status|logs|tools|ai [model]|backup|restore <file>|update|build"; exit 2 }
}
