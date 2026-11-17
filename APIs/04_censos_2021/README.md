# 04 — API Censos de Población y Viviendas 2021

**Qué es.** Endpoint REST `POST https://www.ine.es/Censo2021/api`. El cuerpo contiene `tabla`, `metrica`, `variables` y, opcionalmente, `idioma`. Las listas Excel oficiales son parte del contrato. Se permite entre 1 y 4 variables y sólo dos peticiones concurrentes.

**Caso macro detallado.** El test usa la tabla `per.ocu` para cruzar comunidad autónoma, sexo y rama de actividad (`ID_ACT5`), con la métrica `SPERSONAS`. Responde una pregunta como: *“¿qué estructura sectorial y de género tenía el empleo en cada territorio?”*. La respuesta contiene 228 cruces y permite construir pesos estructurales o segmentar hipótesis de mercado laboral.

No usarlo como señal coyuntural: representa el stock censal de 2021.

**Resultado esperado.** `Metadata` describe las columnas y `Data` devuelve una fila por cruce. En la prueba validada devolvió 228 filas.

La prueba reproducible está en `test_poblacion.ps1`.
