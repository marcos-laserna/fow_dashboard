# APIs del INE — exploración para *Series Dashboard*

Fecha de revisión: 2026-10-05.

Este directorio es la primera capa de **extracción documentada** del proyecto. Está pensado para alimentar después una capa transversal de gestión/series (QRES, gráficos y nowcasting), manteniendo siempre el origen, la fecha de descarga, la frecuencia, la unidad y el estado de revisión de cada observación.

## Conclusión ejecutiva

El portal enumera seis entradas, pero representan cuatro fuentes de datos y dos interfaces auxiliares:

| Entrada del portal | Naturaleza real | Valor para Series Dashboard | Recomendación |
| --- | --- | --- | --- |
| API JSON INE | API REST/GET de INEbase | Series oficiales de coyuntura, empleo, salarios, precios, demografía y actividad | **Fuente principal** |
| INEbase OpenAPI | Especificación y Swagger UI de la API JSON | Descubrimiento y validación de endpoints; no es una fuente nueva | Usar en desarrollo |
| INEapir | Paquete R sobre la API JSON | Atajo para prototipos R; misma cobertura y dependencia | Opcional, no como capa base |
| API Censos 2021 | API REST/POST específica | Stock estructural y geográfico de población/vivienda; no coyuntura | Complemento para denominadores y segmentación |
| SDMX FMI | Catálogo SDMX DSBB, multifuente | Panel macro nacional interoperable: PIB, empleo, paro, IPC, IPI, costes, fiscal/financiero/exterior | **Fuente principal de panel macro** |
| SDMX ODS | Catálogo SDMX Agenda 2030 | Indicadores estructurales y de inclusión, con menos inmediatez | Complemento temático |

**Decisión de arquitectura:** implementar un único conector para API JSON; OpenAPI sólo lo describe e INEapir sólo lo envuelve. Para nowcasting España, empezar con API JSON (granularidad y automatización) y contrastar/publicar el panel agregado con SDMX FMI. Censos y ODS aportan contexto, no señales de alta frecuencia.

## ¿Qué recurso usar para cada pregunta?

| Si la pregunta es… | Empezar por… | Qué aporta y qué tener en cuenta |
| --- | --- | --- |
| ¿Cómo evolucionan en España el empleo, los precios o el consumo? | **API JSON del INE** | Acceso directo a muchas series de INEbase. Para consumo de hogares, la EPF ofrece gasto anual; el índice mensual de comercio minorista sirve como proxy de ventas, no como gasto semanal de los hogares. |
| ¿Cómo se consulta técnicamente la API JSON o cómo la uso desde R? | **OpenAPI / INEapir** | OpenAPI documenta y permite probar las peticiones; INEapir facilita consultarlas desde R. Ninguno añade una fuente estadística nueva. |
| ¿Qué características demográficas o laborales hay detrás de las diferencias entre territorios? | **API Censos 2021** | Desgloses estructurales de población por variables como territorio, sexo y actividad; no es una fuente de coyuntura mensual. |
| ¿Cómo se relacionan PIB, empleo, paro, inflación y otros indicadores macroeconómicos? | **SDMX FMI** | Panel macroeconómico estandarizado con indicadores de varias instituciones; conviene comprobar fuente, unidad y frecuencia de cada serie. |
| ¿Cómo progresa España en sostenibilidad, igualdad, educación o inclusión? | **SDMX ODS** | Indicadores vinculados a los Objetivos de Desarrollo Sostenible, adecuados para contexto social y seguimiento de más largo plazo. |

**Regla rápida:** coyuntura y estadísticas nacionales → API JSON; estructura de población → Censo; panorama macroeconómico → SDMX FMI; sostenibilidad e inclusión → SDMX ODS. OpenAPI e INEapir son herramientas de acceso.

## Comparativa operativa

| Criterio | JSON / OpenAPI / INEapir | Censos 2021 | SDMX FMI | SDMX ODS |
| --- | --- | --- | --- | --- |
| Dominio | INEbase completo | Censo 2021 | Macro DSBB nacional | Agenda 2030 España |
| Transporte | GET URL, JSON | POST, JSON | SDMX | SDMX |
| Descubrimiento | operaciones → tablas → grupos/series | Excel de tablas, variables y métricas | catálogo/estructura SDMX | catálogo/estructura SDMX |
| Frecuencia | depende de la operación; útil para mensual/trimestral | corte censal | mixta, por indicador | mixta, generalmente estructural |
| Desagregación | tablas y filtros `tv` | hasta 4 variables | definida por dataset | definida por indicador |
| Riesgo principal | IDs, revisiones, tres backends (Tempus3/PC-Axis/TPX) | sólo POST, máximo 2 peticiones concurrentes | códigos/dimensiones y fuentes múltiples | comparabilidad, cobertura y rezago |
| Encaje nowcasting | Alto | Bajo/medio (features lentas) | Alto para cuadro de mando/validación | Bajo |

## Reglas comunes de ingesta

1. Guardar *raw response* inmutable, URL/cuerpo, timestamp UTC, HTTP status y hash.
2. Normalizar a observación larga: `source, dataset, series_key, period, value, unit, frequency, adjustment, status, retrieved_at`.
3. No interpretar un último dato como definitivo: conservar `TipoDato`, notas y vintage de descarga.
4. Separar índice, nivel, variación mensual, trimestral e interanual; jamás agregarlos como si fueran la misma medida.
5. Aplicar *rate limiting*, reintentos exponenciales y caché. Para Censos, no superar dos peticiones simultáneas.
6. Validar frecuencia, cobertura temporal, unidad y duplicados antes de cargar QRES.

## Evidencia de viabilidad

El 2026-10-05 se validaron en lectura los dos endpoints que permiten prueba automática:

- `DATOS_TABLA/50902?nult=1` respondió 52 series (IPC).
- `POST https://www.ine.es/Censo2021/api` con `per.ppal`, `SPERSONAS`, residencia y sexo respondió 38 filas.

Los casos por fuente están en sus subcarpetas. Los de SDMX se formulan como pruebas de descubrimiento porque el portal enlaza descargas/metadata por categoría y sus códigos deben resolverse contra el catálogo vigente antes de automatizar una URL concreta.

Los dos scripts ejecutables emplean consultas más expresivas que una prueba de conectividad: `01_api_json/test_ipc.ps1` compara inflación regional con filtros y `04_censos_2021/test_poblacion.ps1` cruza territorio, sexo y rama de actividad.

## Fuentes oficiales

- [Portal de datos abiertos del INE](https://www.ine.es/dyngs/DAB/index.htm?cid=1722)
- [Documentación API JSON](https://www.ine.es/dyngs/DAB/index.htm?cid=1099)
- [Ejemplos y filtros de tablas](https://www.ine.es/dyngs/DAB/index.htm?cid=1102)
- [Documentación API Censos 2021](https://www.ine.es/dyngs/DAB/index.htm?cid=1769)
- [Indicadores económicos y financieros / FMI](https://www.ine.es/fmi/nsdp.htm)
- [Indicadores ODS](https://www.ine.es/dyngs/ODS/index.htm)
