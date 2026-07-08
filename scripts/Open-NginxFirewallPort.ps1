<#
.SYNOPSIS
    Abre en el firewall de Windows el puerto TCP usado por nginx (NGINX_PORT, por defecto 8091).

.DESCRIPTION
    Crea reglas de firewall entrantes y salientes para permitir trafico TCP en el puerto
    donde nginx expone el stack de SLC-SIG_platform (ver docker/docker-compose.yml y docker/.env).
    Es idempotente: si las reglas ya existen, no las duplica.

.PARAMETER Port
    Puerto TCP a abrir. Por defecto 8091 (valor de NGINX_PORT en docker/.env).

.EXAMPLE
    .\Open-NginxFirewallPort.ps1
    .\Open-NginxFirewallPort.ps1 -Port 8091
#>

[CmdletBinding()]
param(
    [int]$Port = 8091
)

$ErrorActionPreference = 'Stop'

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdministrator)) {
    Write-Error "Este script debe ejecutarse como Administrador. Vuelve a abrir PowerShell con 'Ejecutar como administrador' e intenta de nuevo."
    exit 1
}

$rules = @(
    @{ DisplayName = "SIG-SLC Nginx $Port Inbound";  Direction = 'Inbound' }
    @{ DisplayName = "SIG-SLC Nginx $Port Outbound"; Direction = 'Outbound' }
)

try {
    foreach ($rule in $rules) {
        $existing = Get-NetFirewallRule -DisplayName $rule.DisplayName -ErrorAction SilentlyContinue

        if ($existing) {
            Write-Host "La regla '$($rule.DisplayName)' ya existe. Se omite." -ForegroundColor Yellow
            continue
        }

        New-NetFirewallRule `
            -DisplayName $rule.DisplayName `
            -Direction $rule.Direction `
            -LocalPort $Port `
            -Protocol TCP `
            -Action Allow `
            -Profile Any | Out-Null

        Write-Host "Regla creada: '$($rule.DisplayName)' ($($rule.Direction), TCP/$Port)" -ForegroundColor Green
    }

    Write-Host "`nPuerto TCP $Port abierto correctamente en el firewall de Windows." -ForegroundColor Cyan
}
catch {
    Write-Error "Fallo al configurar el firewall: $($_.Exception.Message)"
    exit 1
}
