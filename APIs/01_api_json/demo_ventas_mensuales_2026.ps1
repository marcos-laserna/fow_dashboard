$ErrorActionPreference = 'Stop'

$uri = 'https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/75808?nult=12&tip=A'
$response = Invoke-RestMethod -Uri $uri -TimeoutSec 60

$regions = @(
  @{ ApiName = 'Madrid, Comunidad de'; Label = 'Community of Madrid'; Color = [System.Drawing.Color]::FromArgb(47, 102, 161) }
  @{ ApiName = 'Comunitat Valenciana'; Label = 'Valencian Community'; Color = [System.Drawing.Color]::FromArgb(225, 137, 51) }
)

$monthlyData = foreach ($region in $regions) {
  $series = $response | Where-Object {
    $_.Nombre -like "$($region.ApiName). Cifra de negocio a precios constantes. Comercio al por menor, excepto de vehículos de motor y motocicletas. General. Índice.*"
  } | Select-Object -First 1

  if (-not $series) {
    throw "Could not find the constant-price retail trade index for $($region.Label)."
  }

  $observations = @($series.Data | Where-Object { $_.Anyo -eq 2026 } | Sort-Object Fecha)
  if ($observations.Count -eq 0) {
    throw "The INE API returned no 2026 observations for $($region.Label)."
  }

  foreach ($observation in $observations) {
    [pscustomobject]@{
      Region = $region.Label
      Month = ([datetime]::Parse($observation.Fecha)).ToString('MMM', [System.Globalization.CultureInfo]::GetCultureInfo('en-US'))
      Date = [datetime]::Parse($observation.Fecha)
      Index = [double]$observation.Valor
      Color = $region.Color
    }
  }
}

if (-not $monthlyData -or @($monthlyData | Select-Object -ExpandProperty Region -Unique).Count -ne 2) {
  throw 'The comparison must contain both regions.'
}

Write-Host 'Retail trade sales volume index at constant prices (INE, 2026)' -ForegroundColor Cyan
$monthlyData | Sort-Object Date, Region | Format-Table Month, Region, @{ Label = 'Index (2021 = 100)'; Expression = { '{0:N1}' -f $_.Index } } -AutoSize

# Draw a two-line time series. Labels and chart text are in English.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Windows.Forms.DataVisualization

$chart = New-Object System.Windows.Forms.DataVisualization.Charting.Chart
$chart.Dock = [System.Windows.Forms.DockStyle]::Fill
$chart.BackColor = [System.Drawing.Color]::White
$chart.Width = 1000
$chart.Height = 600

$area = New-Object System.Windows.Forms.DataVisualization.Charting.ChartArea('Main')
$area.AxisX.MajorGrid.Enabled = $false
$area.AxisX.Interval = 1
$area.AxisY.MajorGrid.LineColor = [System.Drawing.Color]::Gainsboro
$area.AxisY.Minimum = 0
$area.AxisY.Maximum = 140
$area.AxisY.Interval = 20
$area.AxisY.Title = 'Index (2021 = 100)'
$chart.ChartAreas.Add($area)

$chart.Titles.Add('Retail trade sales volume index — 2026') | Out-Null
$chart.Titles[0].Font = New-Object System.Drawing.Font('Segoe UI', 16, [System.Drawing.FontStyle]::Bold)
$chart.Titles.Add('Monthly index at constant prices; not household expenditure in euros') | Out-Null
$chart.Titles[1].Font = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Regular)
$chart.Legends.Add('Regions') | Out-Null

foreach ($region in $regions) {
  $line = New-Object System.Windows.Forms.DataVisualization.Charting.Series($region.Label)
  $line.ChartType = [System.Windows.Forms.DataVisualization.Charting.SeriesChartType]::Line
  $line.BorderWidth = 3
  $line.Color = $region.Color
  $line.MarkerStyle = [System.Windows.Forms.DataVisualization.Charting.MarkerStyle]::Circle
  $line.MarkerSize = 7
  $line.Legend = 'Regions'

  $regionPoints = $monthlyData | Where-Object Region -eq $region.Label | Sort-Object Date
  foreach ($point in $regionPoints) {
    [void]$line.Points.AddXY($point.Month, $point.Index)
  }
  $chart.Series.Add($line)
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'INE — Retail Trade Index, 2026'
$form.Width = 1060
$form.Height = 700
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$form.Controls.Add($chart)
[void]$form.ShowDialog()
