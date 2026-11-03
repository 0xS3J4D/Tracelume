# Tracelume launcher for Windows (PowerShell). Requires Docker Desktop.
#   powershell -ExecutionPolicy Bypass -File .\tracelume.ps1 start
param([string]$Command = "start", [string]$Arg = "")
# Native commands (docker) write progress to stderr; don't turn that into terminating errors.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$Port = if ($env:TRACELUME_PORT) { $env:TRACELUME_PORT } else { "8080" }
$Url = "http://127.0.0.1:$Port"
New-Item -ItemType Directory -Force import, backups | Out-Null
if (-not (Test-Path import\synthetic-android.zip)) { Copy-Item demo\synthetic-android.zip import\ -ErrorAction SilentlyContinue }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker is not installed. Install Docker Desktop: https://www.docker.com/products/docker-desktop/" -ForegroundColor Red
  exit 1
}
$null = & docker info 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "Docker Desktop is not running." -ForegroundColor Red
  Write-Host "Open Docker Desktop from the Start menu, wait until it shows 'Engine running', then run this again."
  exit 1
}

function Get-Images([string[]]$Extra) {
  docker compose @Extra pull --quiet --ignore-pull-failures
  docker compose @Extra up --no-start --no-build *> $null
  if ($LASTEXITCODE -ne 0) { docker compose @Extra up --no-start }
}

$CoreTools = @("aleapp", "ileapp", "sqlite-recover", "media", "sleuthkit", "yara")
function Get-CoreTools {
  Write-Host "Preparing core forensic tools (first run may take a few minutes)..."
  docker compose --profile tools pull --quiet --ignore-pull-failures @CoreTools
  docker compose --profile tools up --no-start @CoreTools *> $null
  docker compose --profile tools rm -f @CoreTools *> $null
}

switch ($Command) {
  "start" {
    Get-Images @()
    Get-CoreTools
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
