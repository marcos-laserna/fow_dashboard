# 02 — INEbase OpenAPI

**Qué es.** La interfaz Swagger/OpenAPI de la API JSON, no una sexta base de datos. URL: `https://www.ine.es/OpenAPI/index.html`.

**Uso en el proyecto.** Fuente de verdad para contrato, parámetros y respuestas durante desarrollo; se puede generar cliente o pruebas de contrato. La extracción productiva debe reutilizar el conector de `01_api_json`.

**Caso macro.** Prueba de contrato del flujo IPC: comprobar en Swagger la operación equivalente a `DATOS_TABLA`, ejecutar con tabla 50902 y comparar que llega un array de series con `COD`, `Nombre` y `Data[].Valor`.

**Criterio de aceptación.** Ninguna divergencia de endpoint, parámetros ni esquema respecto al conector JSON. Si cambia el contrato, abrir revisión antes de actualizar pipelines.
