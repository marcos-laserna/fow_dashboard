$ErrorActionPreference = 'Stop'
$body = @{ idioma = 'ES'; metrica = @('SPERSONAS'); tabla = 'per.ocu'; variables = @('ID_RESIDENCIA_N1', 'ID_SEXO', 'ID_ACT5') } | ConvertTo-Json -Compress
$response = Invoke-RestMethod -Uri 'https://www.ine.es/Censo2021/api' -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 60
if (-not $response.Metadata -or -not $response.Data -or $response.Data.Count -eq 0) { throw 'Respuesta censal sin Metadata o Data.' }
if ($response.Metadata.Count -ne 3) { throw 'Las tres variables solicitadas no se reflejan en Metadata.' }
if ($response.Data.Count -ne 228) { throw 'Se esperaban 228 cruces de comunidad, sexo y actividad.' }

# Caso de uso: mapa del empleo censal por territorio, sexo y rama de actividad.
# Es una fotografía estructural de 2021, no un indicador coyuntural mensual.
$response.Data |
  Group-Object ID_ACT5 |
  ForEach-Object {
    [pscustomobject]@{
      RamaActividad = $_.Name
      PersonasCensadas = [math]::Round((($_.Group | Measure-Object SPERSONAS -Sum).Sum), 0)
      Cruces = $_.Count
    }
  } |
  Sort-Object PersonasCensadas -Descending |
  Format-Table -AutoSize
