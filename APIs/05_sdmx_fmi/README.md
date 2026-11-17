# 05 — SDMX FMI / DSBB

**Qué es.** Catálogo nacional de indicadores económicos y financieros publicado bajo el estándar DSBB del FMI y descargable como SDMX. Reúne datos del INE, Banco de España, IGAE y AEAT: es una recopilación, no sólo una fuente INE.

**Caso macro.** Panel España para nowcasting y control de coherencia: PIB/cuentas nacionales (NAG), producción industrial (IND), empleo/desempleo (EMP/UEM), costes laborales (WOE), IPC/PPI (CPI/PPI), más fiscal, financiero y exterior cuando convenga. La clave del modelo será alinear frecuencia y *vintage*, no mezclar publicaciones de distinto calendario.

**Prueba exploratoria de descubrimiento.**

1. Abrir [la página DSBB](https://www.ine.es/fmi/nsdp.htm) y seleccionar la categoría (por ejemplo, `CPI` o `EMP`).
2. Descargar la estructura/metadatos SDMX desde el enlace de la categoría y registrar dataflow, dimensiones, codelists, unidad, ajuste y frecuencia.
3. Pedir una serie mensual/trimestral acotada, parsearla con un cliente SDMX y verificar: fechas únicas, unidad constante, frecuencia documentada y fuente preservada.
4. Guardar la consulta exacta y un snapshot; sólo después promoverla al scheduler.

**Criterio de aceptación.** El flujo conserva la procedencia institucional de cada serie y no completa ausencias mezclando fuentes. Para series de INE que existan en ambos canales, comparar último período, unidad y revisión con API JSON.

Ver [`test_panel_nowcasting.md`](test_panel_nowcasting.md) para un caso de uso concreto.
