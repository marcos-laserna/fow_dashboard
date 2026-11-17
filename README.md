# Series Dashboard

Proyecto de análisis de indicadores económicos y laborales. La exploración de las
fuentes del INE está en [`APIs/`](APIs/).

## Ingesta inicial

`ingest.py` descarga la serie mensual de ventas minoristas de Madrid configurada
en [`data/series.json`](data/series.json) y lee los Excel de [`data/manual/`](data/manual/).
El resultado normalizado se guarda en `data/processed/observations.csv`.

Para cargar una serie manual, copia `data/manual/plantilla_serie.xlsx`, rellena la
hoja `datos` y añade el archivo a `data/manual/`. GitHub Actions está configurado
para ejecutar la ingesta al cambiar esos archivos y una vez al día. La primera
ejecución ya se completó correctamente en GitHub Actions.

La demo del dashboard está en `site/`. `data/manual/mock_serie_prueba.xlsx`
contiene valores sintéticos para probar la segunda línea. Ejecuta `preview.ps1`
en Windows y abre `http://127.0.0.1:8765`. El botón **Actualizar datos** consulta
las últimas observaciones del INE para esta sesión; **Descargar CSV** exporta las
dos series visibles. El refresco manual del navegador no modifica el histórico
del repositorio.

GitHub Pages no está habilitado: el plan actual no admite publicarlo desde este
repositorio privado. Su workflow queda manual hasta que se resuelva esa limitación.

El workflow conserva los datos procesados en Git. Si el Excel contiene datos
privados, el repositorio de GitHub debe ser privado: borrar un archivo en un
commit posterior no elimina sus versiones del historial.

## Estructura

- `APIs/`: documentación y ejemplos de acceso a estadísticas públicas.
- `Automatizaciones/`: procesos de actualización de indicadores.
- `data/manual/`: entradas Excel aportadas manualmente y plantilla.
- `data/processed/`: tabla normalizada generada por la ingesta.
- `.github/workflows/ingest.yml`: planificación y ejecución en GitHub Actions.
