# Sincronización de Drive

| Pestaña | Carpeta de Drive | Destino en el repositorio |
| --- | --- | --- |
| Big Data | [Big Data](https://drive.google.com/drive/folders/1thGWH7iyzwmC3YDjMHf1J_vwmPfNpm8H) | `drive_data/bigdata/` |
| Datos manuales | [Manual](https://drive.google.com/drive/folders/1U8giN5bJ4tJLAtVf_rjlxLu9s6qGr3u2) | `manual_csv/` para CSV y `drive_data/manual/` para la hoja de prueba |
| Turquía | Propiedad `DRIVE_TURKEY_FOLDER_ID`, pendiente de configurar | `turkey_csv/` |

Las rutas de GitHub son relativas a `site/drive_processing/` en `main` de `marcos-laserna/fow_dashboard`.

Big Data lee `Tabla_monitor.csv` para el mapa de calor y `Datos_informe.csv` para los gráficos diarios de consumo y los territorios. Manual importa los CSV de su carpeta y muestra dos series de prueba de la hoja «Alta Frecuencia - España». Los XLSX fechados son archivos históricos. Manual y Turquía aceptan un CSV por serie con columnas `fecha` y `valor` y metadatos opcionales de unidad y frecuencia.

En el proyecto de Apps Script existente, sustituye el código por `DriveToGitHubSync.gs` y guarda. Conserva `GITHUB_TOKEN` con permisos de lectura y escritura de Contents. Ejecuta `syncDriveToGitHub` una vez. Si el disparador ya está instalado, seguirá ejecutando la función cada cinco minutos. Para instalarlo, ejecuta `installDriveSyncTrigger`.

Cada sincronización con cambios crea un commit con los archivos y manifiestos. GitHub Actions procesa ese commit y lanza Pages al terminar. Los datos sincronizados se publican en el repositorio.
