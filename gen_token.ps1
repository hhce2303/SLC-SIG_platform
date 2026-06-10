# gen_token.ps1 — Genera un JWT access token para un usuario del proyecto
# Uso: .\gen_token.ps1            (usa user_id=102 por defecto)
#      .\gen_token.ps1 -UserId 5  (usuario especifico)
#
# Despues de ejecutar, usa:
#   Invoke-ChatRequest "tu mensaje aqui"
# (definida como funcion global en esta sesion)

param(
    [int]$UserId = 102,
    [string]$ApiBase = "http://localhost:8000"
)

$rawOut = docker exec SIGplatform-web python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.production')
django.setup()
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
User = get_user_model()
try:
    u = User.objects.get(id=$UserId)
    print(str(AccessToken.for_user(u)))
except User.DoesNotExist:
    print('ERROR: usuario id=$UserId no existe')
"
# docker exec on Windows may return an array ["eyJ...", ""] due to CRLF;
# join and trim to always get a clean single-line string.
$token = ($rawOut -join '').Trim()

# A valid JWT always starts with "eyJ". Anything else is an error.
if ($token -notlike "eyJ*") {
    Write-Host "ERROR generando token:" -ForegroundColor Red
    Write-Host $token -ForegroundColor Red
    Write-Host "(El contenedor puede estar todavia iniciando. Espera unos segundos y reintenta.)" -ForegroundColor Yellow
    return
}
$global:jwtToken = $token
$global:jwtApiBase = $ApiBase

Write-Host ""
Write-Host "Token generado (valido 60 min):" -ForegroundColor Green
Write-Host $token -ForegroundColor Cyan
Write-Host ""
Write-Host "Guardado en `$global:jwtToken" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Ejemplo:" -ForegroundColor Yellow
Write-Host "  Invoke-ChatRequest `"genera endpoint para listar sitios de sigtools beta`"" -ForegroundColor White
Write-Host "  Invoke-AuditList                  # ver ultimos 10 codegen audits" -ForegroundColor White
Write-Host "  Invoke-AuditList -Last 20 -Status pending  # filtrar por estado" -ForegroundColor White
Write-Host ""

# Copia al portapapeles automaticamente
$token | Set-Clipboard
Write-Host ">> Copiado al portapapeles." -ForegroundColor DarkGray

# Emite el token al pipeline para permitir: $t = (.\gen_token.ps1)
Write-Output $token

# ─── Helper: llama al chatbot con Invoke-RestMethod (timeout 5 min) ──────────
function global:Invoke-ChatRequest {
    param(
        [Parameter(Mandatory)][string]$Message,
        [string]$Api = $global:jwtApiBase
    )
    if (-not $global:jwtToken) {
        Write-Host "ERROR: Ejecuta primero .\gen_token.ps1" -ForegroundColor Red
        return
    }
    $escapedMsg = $Message.Replace('\', '\\').Replace('"', '\"')
    $body = "{`"message`":`"$escapedMsg`",`"history`":[]}"

    try {
        Invoke-RestMethod `
            -Uri     "$Api/api/v1/chatbot/message/" `
            -Method  POST `
            -Headers @{ Authorization = "Bearer $global:jwtToken" } `
            -ContentType "application/json" `
            -Body    $body `
            -TimeoutSec 300
    }
    catch {
        $status = $_.Exception.Response.StatusCode.value__
        $detail = $_.ErrorDetails.Message
        Write-Host "HTTP $status : $detail" -ForegroundColor Red
    }
}

# ─── Helper: ver detalle de un audit de codegen (incluye código generado) ─────
function global:Invoke-AuditDetail {
    param([Parameter(Mandatory)][int]$Id)
    if (-not $global:jwtToken) { Write-Host "ERROR: Ejecuta primero .\gen_token.ps1" -ForegroundColor Red; return }
    $r = Invoke-RestMethod `
        -Uri     "$global:jwtApiBase/api/v1/codegen/audits/$Id/" `
        -Method  GET `
        -Headers @{ Authorization = "Bearer $global:jwtToken" } `
        -TimeoutSec 30
    # Mostrar el código generado legiblemente
    Write-Host "" 
    Write-Host "=== Audit $Id — $($r.status.ToUpper()) ===" -ForegroundColor Cyan
    Write-Host "App      : $($r.targetApp)" -ForegroundColor DarkGray
    Write-Host "Request  : $($r.userRequest)" -ForegroundColor Yellow
    Write-Host "Creado   : $($r.createdAt)" -ForegroundColor DarkGray
    if ($r.deployError) { Write-Host "Error    : $($r.deployError)" -ForegroundColor Red }
    $code = if ($r.finalCode.PSObject.Properties.Count -gt 0) { $r.finalCode } else { $r.generatedCode }
    if ($code.PSObject.Properties.Count -eq 0) {
        Write-Host "`n(Sin codigo generado en este audit)" -ForegroundColor DarkGray
    }
    else {
        foreach ($file in $code.PSObject.Properties) {
            Write-Host "`n--- $($file.Name) ---" -ForegroundColor Green
            Write-Host $file.Value
        }
    }
}

# ─── Helper: listar todos los audits de codegen ───────────────────────────────
function global:Invoke-AuditList {
    param(
        [string]$Api = $global:jwtApiBase,
        [int]   $Last = 10,
        [string]$Status = ""          # filtra por: pending | approved | deployed | rejected
    )
    if (-not $global:jwtToken) { Write-Host "ERROR: Ejecuta primero .\gen_token.ps1" -ForegroundColor Red; return }

    $r = Invoke-RestMethod `
        -Uri     "$Api/api/v1/codegen/audits/" `
        -Method  GET `
        -Headers @{ Authorization = "Bearer $global:jwtToken" } `
        -TimeoutSec 30

    $items = $r.data
    if ($Status) { $items = $items | Where-Object { $_.status -eq $Status } }

    $items = $items | Select-Object -Last $Last

    Write-Host ""
    Write-Host "=== Audits de Codegen (ultimos $Last) ===" -ForegroundColor Cyan
    foreach ($a in $items) {
        $color = switch ($a.status) {
            "deployed" { "Green" }
            "approved" { "DarkGreen" }
            "pending" { "Yellow" }
            "rejected" { "Red" }
            default { "Gray" }
        }
        Write-Host ("[ID:{0,-4}] [{1,-8}] [{2,-12}] {3}" -f $a.id, $a.status.ToUpper(), $a.targetApp, $a.userRequest) -ForegroundColor $color
    }
    Write-Host ""
    Write-Host "Usa: Invoke-AuditDetail <ID>   para ver el codigo generado" -ForegroundColor DarkGray
    Write-Host "Usa: Invoke-Approve <ID>        para aprobar y desplegar" -ForegroundColor DarkGray
}

# ─── Helper: aprobar y desplegar un audit de codegen ─────────────────────────
function global:Invoke-Approve {
    param([Parameter(Mandatory)][int]$Id)
    if (-not $global:jwtToken) { Write-Host "ERROR: Ejecuta primero .\gen_token.ps1" -ForegroundColor Red; return }
    try {
        $r = Invoke-RestMethod `
            -Uri     "$global:jwtApiBase/api/v1/codegen/audits/$Id/approve/" `
            -Method  POST `
            -Headers @{ Authorization = "Bearer $global:jwtToken" } `
            -ContentType "application/json" `
            -TimeoutSec 60
        Write-Host "[OK] Audit $Id desplegado — status: $($r.status)" -ForegroundColor Green
        if ($r.deployError) { Write-Host "Deploy error: $($r.deployError)" -ForegroundColor Red }
    }
    catch {
        $status = $_.Exception.Response.StatusCode.value__
        try { $detail = ($_.ErrorDetails.Message | ConvertFrom-Json).detail } catch { $detail = $_.ErrorDetails.Message }
        Write-Host "HTTP $status : $detail" -ForegroundColor Red
        if ($status -eq 500) { Write-Host "(Revisa que el audit tenga codigo generado con Invoke-AuditDetail $Id)" -ForegroundColor Yellow }
    }
}
