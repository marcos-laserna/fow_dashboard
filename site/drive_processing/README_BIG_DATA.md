# Big Data Â· EspaÃ±a

El monitor combina series nacionales de alta frecuencia y datos territoriales de consumo. El flujo sincroniza las fuentes de Drive con `main` y publica este dashboard como subpÃ¡gina independiente. La pÃ¡gina principal del repositorio se conserva.

## Fuentes de Drive

- La hoja nativa `Alta Frecuencia - EspaÃ±a` (carpeta [Alta Frecuencia en Drive](https://drive.google.com/drive/folders/1U8giN5bJ4tJLAtVf_rjlxLu9s6qGr3u2)) se exporta a XLSX. Sus hojas alimentan las series nacionales de consumo, inversiÃ³n y actividad sectorial en `bigdata.json`.
- La carpeta [Big Data en Drive](https://drive.google.com/drive/folders/1thGWH7iyzwmC3YDjMHf1J_vwmPfNpm8H) contiene `Datos_informe.csv`, con las series diarias territoriales, y `Tabla_monitor.csv`, con las cifras mensuales y semanales del monitor. Ambos se versionan en `drive_data/bigdata/`.
- Las copias XLSX territoriales con fecha que aparecen junto a la hoja de alta frecuencia se ignoran. El CSV territorial anterior evita sincronizar varios XLSX grandes y repetidos.

Apps Script sondea las dos carpetas cada cinco minutos. GitHub Actions importa el XLSX, guarda las cifras publicadas de `Tabla_monitor.csv` en la sección `monitor` de `bigdata.json` y convierte `Datos_informe.csv` a `bigdata_geo/`. El mapa de calor prioriza las celdas de `Tabla_monitor.csv` y conserva el histórico de las demás fuentes fuera de los periodos que cubre el CSV. Cuando cambian los archivos generados, GitHub Actions lanza el despliegue de Pages.

Los detalles de instalaciÃ³n estÃ¡n en [`apps_script/README.md`](apps_script/README.md). La futura carpeta de TurquÃ­a se conectarÃ¡ con la propiedad opcional `DRIVE_TURKEY_FOLDER_ID`.

## PublicaciÃ³n y privacidad

La pÃ¡gina estÃ¡ en `https://marcos-laserna.github.io/fow_dashboard/drive_processing/`. El repositorio es pÃºblico: los CSV, el XLSX exportado y los datos generados en la rama tambiÃ©n serÃ¡n pÃºblicos. No sincronices datos que no estÃ©n aprobados para publicarse.
