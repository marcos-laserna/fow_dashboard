# Carga manual desde Excel

Coloca aquí el Excel con la serie y súbelo al repositorio para iniciar la ingesta.
Usa una hoja llamada `datos` (o la primera hoja) con estas columnas:

| period | value | series_name | unit |
| --- | ---: | --- | --- |
| 2025-01 | 100.0 | Mi serie | Índice |

`period` y `value` son obligatorios. `series_name` y `unit` son opcionales; si
faltan, se usan los valores por defecto de `data/series.json`. Se aceptan períodos
mensuales (`AAAA-MM`), trimestrales (`AAAA-T1`…`AAAA-T4`) o fechas (`AAAA-MM-DD`).

`mock_serie_prueba.xlsx` es un ejemplo **completamente sintético** para comprobar
la lectura y el gráfico. No representa ventas observadas. El proceso lo ingiere
igual que cualquier Excel de esta carpeta; puedes conservarlo para la demo o
quitarlo cuando incorpores tu archivo real.

El repositorio debe ser privado si el Excel contiene información que no quieras
hacer pública. Los archivos añadidos aquí se almacenan en el historial de Git.
