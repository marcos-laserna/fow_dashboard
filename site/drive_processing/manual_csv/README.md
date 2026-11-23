# Manual CSV series

This folder contains CSV series from the Manual Drive folder. The dashboard fetches `manifest.json` and each listed CSV. Turkey uses the separate `../turkey_csv/` folder.

Use one CSV per series. Required columns: `fecha`/`date` and `valor`/`value`. Optional columns include `unidad`/`unit`, `frecuencia`/`frequency`, and `id`. Metadata can appear on the first data row. IDs receive a `turquia_` prefix and the series appears in the manual data group.

```csv
fecha,valor,unidad,frecuencia
2025-01-01,42.1,%,M
2025-02-01,43.0,%,M
```

Dates may use `YYYY-MM-DD`, `YYYY-MM`, `YYYY-Q1` through `YYYY-Q4`, or `DD/MM/YYYY`. Supported frequencies are `D`, `M`, and `Q`.

The repository and Pages output are public. Only place data here that is approved for public access.
