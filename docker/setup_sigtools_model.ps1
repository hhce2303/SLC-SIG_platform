# setup_sigtools_model.ps1
# Descarga deepseek-coder-v2:16b y crea el modelo personalizado sigtools-coder
# Ejecutar DESDE el PC donde corre Ollama, o remotamente si Ollama está en LAN.
#
# Uso:
#   .\setup_sigtools_model.ps1                          # Ollama local
#   .\setup_sigtools_model.ps1 -OllamaHost 192.168.101.132:11434  # Ollama remoto

param(
    [string]$OllamaHost = "192.168.101.132:11434",
    [string]$BaseModel  = "deepseek-coder-v2:16b",
    [string]$ModelName  = "sigtools-coder"
)

$base = "http://$OllamaHost"

function Invoke-OllamaPost($path, $body) {
    $json = $body | ConvertTo-Json -Depth 5
    Invoke-WebRequest -Uri "$base$path" -Method POST `
        -Body $json -ContentType "application/json" -UseBasicParsing
}

# Reliable character-by-character JSON string escaper.
# Avoids ConvertTo-Json PS5 bugs and encoding issues with multibyte chars.
function ConvertTo-JsonString([string]$str) {
    $sb = [System.Text.StringBuilder]::new($str.Length * 2)
    foreach ($c in $str.ToCharArray()) {
        $code = [int]$c
        switch ($code) {
             8 { [void]$sb.Append('\b') }
             9 { [void]$sb.Append('\t') }
            10 { [void]$sb.Append('\n') }
            12 { [void]$sb.Append('\f') }
            13 { [void]$sb.Append('\r') }
            34 { [void]$sb.Append('\"') }
            92 { [void]$sb.Append('\\') }
            default {
                if ($code -lt 32) {
                    [void]$sb.Append(('\u{0:x4}' -f $code))
                } else {
                    [void]$sb.Append($c)
                }
            }
        }
    }
    return $sb.ToString()
}

# ─── Step 1: Pull base model ───────────────────────────────────────────────
Write-Host ""
Write-Host ">>> PASO 1: Descargando $BaseModel (~10 GB, puede tardar 30-60 min)..." -ForegroundColor Cyan

$pullBody = @{ name = $BaseModel; stream = $false }
try {
    $r = Invoke-OllamaPost "/api/pull" $pullBody
    Write-Host "    Pull completado. Status: $($r.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "ERROR en pull: $_" -ForegroundColor Red
    exit 1
}

# ─── Step 2: Parse Modelfile ───────────────────────────────────────────────
$scriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$modelfilePath = Join-Path $scriptDir "Modelfile.sigtools-coder"

if (-not (Test-Path $modelfilePath)) {
    Write-Host "ERROR: No se encontro Modelfile.sigtools-coder en $scriptDir" -ForegroundColor Red
    exit 1
}

# Read with explicit UTF-8 (PS5 default is ANSI, corrupts em-dash, arrows, etc.)
$modelfileContent = [System.IO.File]::ReadAllText(
    (Resolve-Path $modelfilePath).Path,
    [System.Text.Encoding]::UTF8
)

# Extract FROM (fall back to $BaseModel param)
$fromModel = $BaseModel
if ($modelfileContent -match '(?m)^FROM\s+(.+)$') { $fromModel = $Matches[1].Trim() }

# Extract SYSTEM block — content between first SYSTEM """ and last """
$sysMarker    = 'SYSTEM """'
$sysStart     = $modelfileContent.IndexOf($sysMarker) + $sysMarker.Length
$sysEnd       = $modelfileContent.LastIndexOf('"""')
$systemPrompt = $modelfileContent.Substring($sysStart, $sysEnd - $sysStart).Trim()

Write-Host "    FROM   : $fromModel" -ForegroundColor DarkGray
Write-Host "    SYSTEM : $($systemPrompt.Length) chars" -ForegroundColor DarkGray

# ─── Step 3: Create custom model (Ollama >=0.5 API: from/system/parameters) ─
Write-Host ""
Write-Host ">>> PASO 2: Creando modelo personalizado '$ModelName'..." -ForegroundColor Cyan

# Ollama >=0.5 dropped the 'modelfile' string field.
# Use structured fields: model, from, system, parameters.
$escapedSystem = ConvertTo-JsonString $systemPrompt
$createJson = '{"model":"' + $ModelName + '","from":"' + $fromModel + '","system":"' + $escapedSystem + '","parameters":{"temperature":0.1,"num_predict":4096,"repeat_penalty":1.1},"stream":false}'

try {
    $r2 = Invoke-WebRequest -Uri "$base/api/create" -Method POST `
        -Body $createJson -ContentType "application/json" -UseBasicParsing
    Write-Host "    Modelo creado. Status: $($r2.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "ERROR creando modelo: $_" -ForegroundColor Red
    exit 1
}

# ─── Step 4: Verify ────────────────────────────────────────────────────────
Write-Host ""
Write-Host ">>> PASO 3: Verificando modelos disponibles..." -ForegroundColor Cyan
$listed = (Invoke-WebRequest -Uri "$base/api/tags" -UseBasicParsing).Content | ConvertFrom-Json
$listed.models | Select-Object name, @{N="GB";E={[math]::Round($_.size/1GB,1)}} | Format-Table

Write-Host "OK  Listo. Actualiza OLLAMA_MODEL=sigtools-coder en el .env del contenedor." -ForegroundColor Green
Write-Host '   Luego: docker compose -f docker/docker-compose.yml restart web' -ForegroundColor Yellow
