# 03 — INEapir (R)

**Qué es.** Paquete oficial de R que envuelve la API JSON: `install.packages("ineapir")`. Aporta funciones de datos y metadatos, no datos distintos.

**Caso macro detallado.** `test_inflacion_regional.R` obtiene 12 observaciones de IPC regional y selecciona la variación anual del índice general para Asturias y Castilla y León. Es una forma cómoda de crear un prototipo de comparación territorial en R. La tabla completa puede traer más series de las necesarias; en producción se deben trasladar los filtros a la petición HTTP.

```r
library(ineapir)
ipc <- get_data_table(idTable = 50902, nlast = 3, tip = "A", unnest = TRUE)
stopifnot(all(c("COD", "Nombre", "Fecha", "Valor") %in% names(ipc)))
```

**Decisión.** Adecuado para exploración individual en R. Para producción multi-lenguaje, conservar el conector HTTP de `01_api_json`, que evita acoplar el pipeline a R y hace equivalentes las implementaciones.

**Riesgos.** El modelo devuelve datos anidados salvo `unnest=TRUE`; validar versiones del paquete y mantener el ID/URL original en la tabla resultante.
