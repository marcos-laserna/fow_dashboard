# Carga manual desde Excel

Coloca aquí archivos Excel con datos sintéticos o públicos. Se lee la hoja `datos` o, si no existe, la primera hoja; los archivos temporales `~$` se ignoran.

Formato largo: encabezados `period` y `value` obligatorios; `series_id`, `series_name` y `unit` son opcionales. Cada combinación de ID o nombre forma una serie.

| period | value | series_name | unit |
| --- | ---: | --- | --- |
| 2025-01 | 100 | Mi serie | Índice |

Formato ancho: primera columna `period` y cada columna restante debe tener el nombre de una serie.

| period | Serie A | Serie B |
| --- | ---: | ---: |
| 2025-01 | 100 | 98 |

Se aceptan períodos mensuales (`AAAA-MM`), trimestrales (`AAAA-T1` o `AAAA-Q1`), anuales (`AAAA`) y fechas (`AAAA-MM-DD`). Si faltan etiquetas o unidades, se usan los valores predeterminados de `data/series.json`.
