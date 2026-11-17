# 01 — API JSON INE

**Qué es.** API GET que expone INEbase en JSON, incluidos los repositorios Tempus3, PC-Axis y TPX. No requiere clave según la documentación pública.

**Patrón.** `https://servicios.ine.es/wstempus/js/{idioma}/{FUNCION}/{id}`. Ejemplo validado: `DATOS_TABLA/50902?nult=1`. El parámetro `nult` limita las últimas observaciones; `tip=A` solicita presentación más legible y `tv=variable:valor` se repite para filtrar.

**Descubrimiento correcto.** 1) operación/tablas, 2) `GRUPOS_TABLA/{id}` o `SERIES_TABLA/{id}?tip=M`, 3) valores de grupo, 4) `DATOS_TABLA`. Los IDs y el dialecto de filtros cambian según backend; no hardcodear un filtro sin inspeccionar antes sus metadatos.

**Demo para presentación.** `demo_ventas_mensuales_2026.ps1` consulta la tabla INE 75808 y compara mes a mes el índice de ventas del comercio minorista a precios constantes en la Comunidad de Madrid y la Comunitat Valenciana. El script imprime los meses disponibles de 2026 y abre un gráfico de líneas con etiquetas en inglés. En la consulta actual hay datos de enero a agosto.

Este índice es un indicador mensual de ventas minoristas, no gasto semanal de los hogares en euros. Se usa como proxy oportuno para comparar la evolución de las ventas entre comunidades. La petición `nult=12` solicita hasta las últimas doce observaciones por serie; el script selecciona las de 2026 y el índice general.

**Ejemplo complementario.** `test_ipc.ps1` compara los últimos 12 meses de inflación anual del IPC general en Asturias y Castilla y León.

El resultado mantiene una serie por comunidad, el período y la variación anual; no confunde el nivel del índice con una tasa de inflación.

**Límites.** Respuestas anidadas por serie; `Valor` es la observación y el resto de campos la define. Registrar `Secreto`, tipo de dato y revisiones. Una tabla puede contener decenas de series: filtrar y usar `nult` antes de descargar.
