# 06 — SDMX ODS

**Qué es.** Servicio SDMX de los indicadores españoles de la Agenda 2030. El INE indica 17 objetivos, 169 metas y 234 indicadores para su seguimiento; incorpora progresivamente datos de INE y otras fuentes oficiales.

**Caso macro.** Módulo estructural de calidad/inclusión del empleo: combinar indicadores de pobreza, educación, igualdad y productividad cuando estén disponibles, documentando indicador, desagregación y periodicidad. Sirve para análisis de tendencias y heterogeneidad territorial, no para nowcasting mensual.

**Prueba exploratoria de descubrimiento.**

1. Seleccionar un indicador con hipótesis explícita —por ejemplo, empleo/educación/desigualdad— desde [el portal ODS](https://www.ine.es/dyngs/ODS/index.htm).
2. Abrir su descarga SDMX y extraer dataflow, DSD, codelists, fuente, unidad, cobertura y desglose territorial/sexo/edad.
3. Descargar un rango pequeño y comprobar que cada observación tiene período, valor, unidad y etiquetas de dimensión resolubles.
4. Marcar los huecos como `missing` (no cero) y la periodicidad real; guardar metadatos junto con los datos.

**Criterio de aceptación.** Una tabla larga y reproducible que permita comparar únicamente observaciones con misma definición/unidad. No usar la etiqueta ODS como sustituto de comparabilidad estadística.

Ver [`test_inclusion_laboral.md`](test_inclusion_laboral.md) para un escenario aplicable a Series Dashboard.
