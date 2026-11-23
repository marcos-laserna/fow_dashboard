# Drive to GitHub sync

`DriveToGitHubSync.gs` polls the supplied Big Data and high-frequency Drive folders every five minutes and optionally a Turkey folder. It pushes changed source files and manifests to `marcos-laserna/fow_dashboard`, branch `main`. It writes only below `site/drive_processing/` in `main`.

## Drive inputs

- Big Data folder: `1thGWH7iyzwmC3YDjMHf1J_vwmPfNpm8H`; required CSVs are `Datos_informe.csv` and `Tabla_monitor.csv`.
- High-frequency folder: `1U8giN5bJ4tJLAtVf_rjlxLu9s6qGr3u2`; the configured native sheet `Alta Frecuencia - EspaÃ±a` is exported to XLSX. Dated XLSX archives are ignored.
- Turkey folder: optional Script Property `DRIVE_TURKEY_FOLDER_ID`, pending its final route. Use one CSV per series with `fecha/date`, `valor/value`, and optional unit/frequency metadata.

## Apps Script setup

1. Create a Google Apps Script project and paste in `DriveToGitHubSync.gs`.
2. Enable the `appsscript.json` manifest view and copy `appsscript.json` into the project.
3. Add `GITHUB_TOKEN` in Project Settings â†’ Script properties. Use a fine-grained token with Contents read/write access to `marcos-laserna/fow_dashboard` on `main`.
4. Run `syncDriveToGitHub` once, approve Drive read and external-request permissions, then run `installDriveSyncTrigger` once.
5. Enable GitHub Actions and confirm the workflow can write to the branch.
6. Add `DRIVE_TURKEY_FOLDER_ID` later when the Turkey folder is ready.

The workflow runs after a source manifest changes. It imports the high-frequency workbook with `importar_bigdata.py`, builds territorial JSON from `Datos_informe.csv`, regenerates the heat map, and rebuilds `espana.html` / `artifact.html`.

The dashboard is published as a separate subpage at `https://marcos-laserna.github.io/fow_dashboard/drive_processing/`. Generated files stay under `site/drive_processing/`; the existing homepage remains in place.

## Turkish CSV format

Use one series per CSV:

```csv
fecha,valor,unidad,frecuencia
2025-01-01,42.1,%,M
2025-02-01,43.0,%,M
```

Accepted English column names are `date`, `value`, `unit`, and `frequency`. Supported frequencies are `D`, `M`, and `Q`. IDs receive the `turquia_` prefix and are grouped under manual data.

## Public data

This repository and its Pages output are public. Synced CSV and XLSX files become public on the branch. Only publish data approved for public access.
