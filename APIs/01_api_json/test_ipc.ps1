$ErrorActionPreference = 'Stop'
$uri = 'https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/50913?nult=12&tip=A&tv=3:74&tv=762:304092&tv=70:9003&tv=70:8999'
$response = Invoke-RestMethod -Uri $uri -TimeoutSec 60
if (-not $response -or $response.Count -eq 0) { throw 'La API no devolvió series.' }
$observations = @($response | ForEach-Object { $_.Data } | Where-Object { $null -ne $_.Valor })
if ($response.Count -ne 2) { throw 'Se esperaban dos comunidades autónomas.' }
if ($observations.Count -ne 24) { throw 'Se esperaban 12 observaciones por comunidad.' }

# Caso de uso: comparar la inflación anual del índice general entre Asturias y Castilla y León.
# tv=3:74                 -> tipo de dato: variación anual
# tv=762:304092           -> grupo ECOICOP: índice general
# tv=70:9003 / tv=70:8999 -> Castilla y León / Asturias
$response | ForEach-Object {
  $latest = $_.Data | Sort-Object Fecha | Select-Object -Last 1
  [pscustomobject]@{
    Serie = $_.Nombre.Trim()
    Periodo = "$($latest.Anyo)-$($latest.T3_Periodo)"
    InflacionAnualPct = $latest.Valor
    Observaciones = $_.Data.Count
  }
} | Format-Table -AutoSize
