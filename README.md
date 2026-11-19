# Series Dashboard

Piloto de visualización de series económicas al estilo Haver: catálogo con buscador,
gráfico de varias series con doble eje, transformaciones (nivel, % periodo anterior,
% interanual, diferencia, base 100) y descarga en CSV o Excel.

Solo contiene datos públicos (INE, Eurostat) y Excel manuales sintéticos de ejemplo.

## Dos interfaces sobre los mismos datos

- **GitHub Pages** (`site/`): web estática; lee `data/processed/catalog.csv` y
  `observations.csv`. La vista se guarda en la URL, así que puedes compartir enlaces.
- **Streamlit** (`app/streamlit_app.py`): misma funcionalidad en Python.

### En local

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r app/requirements.txt
.venv/bin/streamlit run app/streamlit_app.py      # Streamlit
python3 -m http.server 8765                        # Pages: abre http://127.0.0.1:8765/site/
```

## Datos

`python ingest.py` (paquete `pipeline/`) descarga las fuentes de `data/series.json`
y lee los Excel de `data/manual/` (ver su README para el formato). Genera:

- `data/processed/observations.csv`: formato largo, una fila por serie y periodo.
- `data/processed/catalog.csv`: una fila por serie (fuente, grupo, frecuencia, rango).

GitHub Actions ejecuta la ingesta a diario y al cambiar los Excel o la configuración,
y después vuelve a publicar Pages.

Para añadir una serie: una entrada en `sources` de `data/series.json` (tipos
`ine_series`, `ine_general_index`, `ine_catalog`, `eurostat`) o un Excel en `data/manual/`.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest -q
```

## Estructura

- `pipeline/`: ingesta (fuentes, almacenamiento, transformaciones).
- `site/`: dashboard estático para GitHub Pages.
- `app/`: app de Streamlit y sus dependencias.
- `data/`: configuración, Excel manuales y datos procesados.
- `APIs/`: documentación y ejemplos de acceso a estadísticas públicas.
- `tests/`: tests de la ingesta.
