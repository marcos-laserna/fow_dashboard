# Big Data Â· EspaÃ±a

El monitor combina series nacionales de alta frecuencia y datos territoriales de consumo. El flujo sincroniza las fuentes de Drive con `main` y publica este dashboard como subpÃ¡gina independiente. La pÃ¡gina principal del repositorio se conserva.

## Fuentes de Drive

- La hoja nativa `Alta Frecuencia - EspaÃ±a` (carpeta [Alta Frecuencia en Drive](https://drive.google.com/drive/folders/1U8giN5bJ4tJLAtVf_rjlxLu9s6qGr3u2)) se exporta a XLSX. Sus hojas alimentan las series nacionales de consumo, inversiÃ³n y actividad sectorial en `bigdata.json`.
- La carpeta [Big Data en Drive](https://drive.google.com/drive/folders/1thGWH7iyzwmC3YDjMHf1J_vwmPfNpm8H) contiene `Datos_informe.csv`, con observaciones diarias por territorio, y `Tabla_monitor.csv`, con el reporte publicado. Ambos se versionan en `drive_data/bigdata/`; el primero alimenta los datos territoriales y el segundo queda como archivo fuente de referencia.
- Las copias XLSX territoriales con fecha que aparecen junto a la hoja de alta frecuencia se ignoran. El CSV territorial anterior evita sincronizar varios XLSX grandes y repetidos.

Apps Script sondea las dos carpetas cada cinco minutos. Un workflow de GitHub Actions importa el XLSX, convierte el CSV territorial a `bigdata_geo/`, ejecuta `generar_heatmap.py` y regenera `espana.html` y `artifact.html`. El mapa de calor presenta observaciones al cierre de mes y semana; transforma fracciones a porcentaje y combina series BBVA Research con los dos indicadores del INE de `data.json`.

Los detalles de instalaciÃ³n estÃ¡n en [`apps_script/README.md`](apps_script/README.md). La futura carpeta de TurquÃ­a se conectarÃ¡ con la propiedad opcional `DRIVE_TURKEY_FOLDER_ID`.

## PublicaciÃ³n y privacidad

La pÃ¡gina estÃ¡ en `https://marcos-laserna.github.io/fow_dashboard/drive_processing/`. El repositorio es pÃºblico: los CSV, el XLSX exportado y los datos generados en la rama tambiÃ©n serÃ¡n pÃºblicos. No sincronices datos que no estÃ©n aprobados para publicarse.
