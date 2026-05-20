# sync_from_container.ps1
# Copia los archivos de apps/ del contenedor → local
# Usar ANTES de docker compose up --build para no perder cambios del chatbot

$container = "daily-log-backend"
$base      = $PSScriptRoot

Write-Host "Sincronizando apps/ del contenedor al local..." -ForegroundColor Cyan

# Verificar que el contenedor está corriendo
$running = docker inspect -f "{{.State.Running}}" $container 2>$null
if ($running -ne "true") {
    Write-Host "ERROR: El contenedor '$container' no está corriendo." -ForegroundColor Red
    exit 1
}

# Ver qué archivos cambió el chatbot vs local (git diff)
$gitDiff = git -C $base diff --name-only HEAD 2>$null
if ($gitDiff) {
    Write-Host "`nArchivos modificados localmente (git):" -ForegroundColor Yellow
    $gitDiff | ForEach-Object { Write-Host "  $_" }
}

# Copiar apps/ completo del contenedor → local
$tmpDir = "$env:TEMP\container_apps_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

Write-Host "`nDescargando apps/ del contenedor..." -ForegroundColor Cyan
docker cp "${container}:/app/apps/." "$tmpDir"

# Comparar y copiar solo archivos que difieren
$changed = @()
Get-ChildItem -Recurse -File $tmpDir | Where-Object { $_.Extension -ne ".pyc" -and $_.DirectoryName -notlike "*__pycache__*" } | ForEach-Object {
    $rel     = $_.FullName.Substring($tmpDir.Length + 1) -replace '\\', '/'
    $local   = Join-Path $base "apps\$rel"
    $fromContainer = $_.FullName

    if (-not (Test-Path $local)) {
        # Archivo nuevo creado por el chatbot
        $dir = Split-Path $local -Parent
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Copy-Item $fromContainer $local
        $changed += "  [NUEVO]    apps/$rel"
    } else {
        $hashLocal     = (Get-FileHash $local     -Algorithm MD5).Hash
        $hashContainer = (Get-FileHash $fromContainer -Algorithm MD5).Hash
        if ($hashLocal -ne $hashContainer) {
            Copy-Item $fromContainer $local
            $changed += "  [MODIFICADO] apps/$rel"
        }
    }
}

Remove-Item $tmpDir -Recurse -Force

if ($changed.Count -eq 0) {
    Write-Host "`nSin diferencias - el local ya esta al dia." -ForegroundColor Green
} else {
    Write-Host "`nArchivos sincronizados desde el contenedor:" -ForegroundColor Green
    $changed | ForEach-Object { Write-Host $_ }
    Write-Host "`nRevisa los cambios y luego haz: docker compose up --build -d" -ForegroundColor Cyan
}
