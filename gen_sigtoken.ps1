# gen_sigtoken.ps1 — Login via SigTools cookie auth
# Usa HttpClient (no HttpWebRequest) para evitar bugs de PS5 con SameSite=Lax.
# Guarda el token en $global:sigToken para reusarlo con Invoke-SigRequest.
#
# Uso:
#   .\gen_sigtoken.ps1 -Pass "tu_pass"
#
# Luego:
#   Invoke-SigRequest POST chatbot/message/ '{"message":"...","history":[]}'

param(
    [string]$User = "dcarvajal",
    [string]$Pass = "",
    [string]$ApiBase = "http://localhost"
)

# Cargar el assembly explicitamente (PS5 no lo carga por defecto)
Add-Type -AssemblyName "System.Net.Http"

if ($Pass -eq "") {
    $securePwd = Read-Host "Password para $User" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePwd)
    $Pass = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

# HttpClient no tiene los bugs de HttpWebRequest con SameSite/Authorization
$http = [System.Net.Http.HttpClient]::new()
$loginJson = [System.Net.Http.StringContent]::new(
    "{`"username`":`"$User`",`"password`":`"$Pass`"}",
    [System.Text.Encoding]::UTF8,
    "application/json"
)

try {
    $resp = $http.PostAsync("$ApiBase/api/v1/web-auth/login/", $loginJson).Result

    if (-not $resp.IsSuccessStatusCode) {
        Write-Host "ERROR en login ($($resp.StatusCode)): $($resp.Content.ReadAsStringAsync().Result)" -ForegroundColor Red
        exit 1
    }

    $body = $resp.Content.ReadAsStringAsync().Result | ConvertFrom-Json
    $global:sigToken = $body.access_token
    $global:sigApiBase = $ApiBase
    $global:sigHttp = $http

    # Fijar el header por defecto para todos los requests de este cliente
    $http.DefaultRequestHeaders.Authorization =
    [System.Net.Http.Headers.AuthenticationHeaderValue]::new("Bearer", $global:sigToken)

    $uname = if ($body.user.name) { $body.user.name } else { $User }

    # Copiar solo el token al clipboard (listo para pegar en Postman → Bearer Token)
    Set-Clipboard -Value $global:sigToken

    Write-Host ""
    Write-Host "Login OK: $uname" -ForegroundColor Green
    Write-Host "Token capturado en `$global:sigToken" -ForegroundColor Cyan
    Write-Host "Token (sin 'Bearer') copiado al clipboard " -ForegroundColor Magenta -NoNewline
    Write-Host "`u{2713}" -ForegroundColor Green
    Write-Host "  → Postman: Auth Type = Bearer Token, pega el clipboard en 'Token'" -ForegroundColor DarkGray
    Write-Host "  → curl:    -H `"Authorization: Bearer `$(Get-Clipboard)`"" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "Ejemplo (usa Invoke-SigRequest definida abajo):" -ForegroundColor Yellow
    Write-Host "  Invoke-SigRequest POST chatbot/message/ '{`"message`":`"genera endpoint cameras`",`"history`":[]}'" -ForegroundColor White
    Write-Host ""

}
catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    exit 1
}

# ─── Helper reutilizable en esta sesión ────────────────────────────────────
function global:Invoke-SigRequest {
    param(
        [string]$Method = "GET",
        [string]$Path,          # ej: "chatbot/message/"
        [string]$Body = ""
    )
    $uri = "$global:sigApiBase/api/v1/$Path"
    if ($Method -eq "GET") {
        $r = $global:sigHttp.GetAsync($uri).Result
    }
    else {
        $content = [System.Net.Http.StringContent]::new(
            $Body, [System.Text.Encoding]::UTF8, "application/json"
        )
        $r = $global:sigHttp.PostAsync($uri, $content).Result
    }
    $r.Content.ReadAsStringAsync().Result
}

