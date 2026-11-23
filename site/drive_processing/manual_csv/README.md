# Manual CSV series

This folder is the handoff point for manual series. Apps Script writes Turkey series here when `DRIVE_TURKEY_FOLDER_ID` is configured. The dashboard fetches `manifest.json` and each listed CSV.

Use one CSV per series. Required columns: `fecha`/`date` and `valor`/`value`. Optional columns include `unidad`/`unit`, `frecuencia`/`frequency`, and `id`. Metadata can appear on the first data row. IDs receive a `turquia_` prefix and the series appears in the manual data group.

```csv
fecha,valor,unidad,frecuencia
2025-01-01,42.1,%,M
2025-02-01,43.0,%,M
```

Dates may use `YYYY-MM-DD`, `YYYY-MM`, `YYYY-Q1` through `YYYY-Q4`, or `DD/MM/YYYY`. Supported frequencies are `D`, `M`, and `Q`.

The repository and Pages output are public. Only place data here that is approved for public access.
