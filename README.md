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
ejecución depende de publicar este repositorio en GitHub.

El workflow conserva los datos procesados en Git. Si el Excel contiene datos
privados, el repositorio de GitHub debe ser privado: borrar un archivo en un
commit posterior no elimina sus versiones del historial.

## Estructura

- `APIs/`: documentación y ejemplos de acceso a estadísticas públicas.
- `Automatizaciones/`: procesos de actualización de indicadores.
- `data/manual/`: entradas Excel aportadas manualmente y plantilla.
- `data/processed/`: tabla normalizada generada por la ingesta.
- `.github/workflows/ingest.yml`: planificación y ejecución en GitHub Actions.
