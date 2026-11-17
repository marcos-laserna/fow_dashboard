$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$siteData = Join-Path $root 'site/data'
$sourceCsv = Join-Path $root 'data/processed/observations.csv'
$targetCsv = Join-Path $siteData 'observations.csv'

if (-not (Test-Path -LiteralPath $sourceCsv)) {
    throw "No existe el CSV de ingesta: $sourceCsv"
}

New-Item -ItemType Directory -Path $siteData -Force | Out-Null
Copy-Item -LiteralPath $sourceCsv -Destination $targetCsv -Force
Write-Host 'Dashboard local: http://127.0.0.1:8765'
Write-Host 'Pulsa Ctrl+C para detener el servidor.'
Set-Location -LiteralPath $root
python -m http.server 8765 --directory site
