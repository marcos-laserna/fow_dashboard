# Guía sencilla: qué ofrece cada acceso a datos del INE

## La idea en una frase

El INE ofrece una gran biblioteca de estadísticas. Las seis opciones del portal no son seis bibliotecas distintas: son distintas **puertas de acceso** y formatos para consultar esa información según la necesidad.

Para *Series Dashboard*, usaremos las puertas más adecuadas para responder dos tipos de pregunta:

1. **¿Qué está ocurriendo ahora en la economía y el empleo?**
2. **¿Qué características estructurales tiene la población y el mercado laboral?**

## Mapa rápido

| Opción | Explicación intuitiva | Para qué sirve en el proyecto |
| --- | --- | --- |
| API JSON INE | La puerta principal a la biblioteca estadística del INE | Descargar automáticamente datos recientes de empleo, precios, salarios, actividad y demografía |
| INEbase OpenAPI | El manual interactivo de esa puerta principal | Ayuda al equipo técnico a saber cómo pedir cada dato correctamente |
| INEapir | Un mando a distancia para analistas que trabajan en R | Facilita análisis y prototipos en R, sin añadir datos nuevos |
| API Censos 2021 | Un atlas detallado de la población española en 2021 | Entender el contexto territorial y demográfico detrás de las cifras de empleo |
| SDMX FMI | Un cuadro de mando macroeconómico estandarizado | Seguir y comparar PIB, inflación, empleo, producción y variables financieras con una estructura común |
| SDMX ODS | Un marcador de progreso social y sostenible | Añadir la perspectiva de inclusión, igualdad, educación y sostenibilidad al análisis de largo plazo |

## Las seis opciones, explicadas sin tecnicismos

### 1. API JSON INE: la puerta principal

Imaginemos INEbase como una biblioteca enorme. La API JSON es el mostrador donde se puede pedir: “dame las últimas cifras de inflación”, “dame empleo por sector” o “dame esta serie para cada comunidad autónoma”.

Es la opción más útil para automatizar la recogida frecuente de datos. En vez de que una persona descargue manualmente un Excel cada mes, el sistema puede consultar la fuente oficial, guardar el resultado y actualizar los gráficos.

**Ejemplo para el cliente:** cada vez que el INE publique el IPC, el proyecto puede recoger la cifra, compararla con el mes anterior y actualizar el seguimiento de coste de vida y poder adquisitivo.

### 2. INEbase OpenAPI: el manual de instrucciones

No es otra fuente de estadísticas. Es el manual interactivo que explica cómo usar la API JSON: qué se puede pedir, cómo se llama cada campo y qué respuesta esperar.

**Ejemplo para el cliente:** equivale al índice y las instrucciones de la biblioteca. No genera una nueva cifra de paro; ayuda a que el equipo solicite correctamente la cifra de paro que ya publica el INE.

### 3. INEapir: el atajo para R

Tampoco añade datos nuevos. Es una herramienta preparada para quienes analizan datos con el lenguaje R. Simplifica el trabajo técnico de convertir una consulta al INE en una tabla lista para analizar.

**Ejemplo para el cliente:** es como tener un adaptador para usar la misma toma de corriente con un tipo concreto de equipo. Resulta cómodo para analistas R, pero la electricidad —los datos— es la misma que llega por la API JSON.

### 4. API de Censos 2021: la fotografía detallada

El Censo ofrece una fotografía muy detallada de cómo era la población y las viviendas en 2021: edad, sexo, territorio y otras características. No está pensado para seguir cambios mes a mes, sino para dar contexto.

**Ejemplo para el cliente:** si dos comunidades muestran una tasa de empleo distinta, el Censo ayuda a entender su base demográfica: cuánta población hay, cómo se distribuye por edad y sexo, o cómo es el territorio.

### 5. SDMX FMI: el cuadro de mando económico común

SDMX es un idioma estándar para intercambiar estadísticas. El servicio vinculado al FMI reúne indicadores económicos y financieros de España en ese formato común: PIB, empleo, desempleo, inflación, producción industrial, costes laborales y más.

No significa que todo lo produzca el INE: integra fuentes oficiales como el INE, Banco de España, IGAE y AEAT. Su ventaja es que las cifras se organizan de forma homogénea, lo que facilita construir un panel macroeconómico y compararlo con otros países o fuentes que usan el mismo estándar.

**Ejemplo para el cliente:** un tablero ejecutivo que muestre, de forma coherente, crecimiento, inflación, empleo y producción; útil para seguir el entorno en el que evoluciona el mercado de trabajo.

### 6. SDMX ODS: el marcador de progreso social

Este servicio organiza los indicadores españoles relacionados con los Objetivos de Desarrollo Sostenible de la Agenda 2030. Permite observar temas como inclusión, igualdad, educación, pobreza y sostenibilidad.

Son indicadores más estructurales y menos inmediatos que el IPC o el paro mensual. Por eso complementan un análisis de futuro del trabajo, pero no sustituyen a la información coyuntural.

**Ejemplo para el cliente:** analizar si una mejora agregada del empleo llega por igual a diferentes grupos de población y territorios, o si persisten brechas que importan para la estrategia de talento.

## Qué utilizaremos y por qué

| Necesidad | Fuente recomendada | Motivo |
| --- | --- | --- |
| Actualizar indicadores frecuentes de empleo, precios o actividad | API JSON INE | Es la puerta más directa y flexible a las series oficiales |
| Construir una visión macroeconómica completa | SDMX FMI | Reúne indicadores de varios organismos en un estándar común |
| Contextualizar diferencias territoriales y demográficas | API Censos 2021 | Aporta el detalle estructural que no aparece en la coyuntura mensual |
| Incorporar impacto social a largo plazo | SDMX ODS | Añade inclusión y sostenibilidad |
| Facilitar el desarrollo técnico o análisis en R | OpenAPI e INEapir | Son herramientas de apoyo; no fuentes adicionales |

## Mensaje final para la exposición

> No estamos eligiendo entre seis conjuntos de datos que compiten entre sí. Estamos combinando una puerta principal para datos actualizados, un cuadro de mando macroeconómico estandarizado y dos fuentes de contexto estructural. Las otras dos opciones son herramientas para que el equipo técnico acceda a la misma información de forma segura y reproducible.

## Garantías de uso responsable

- Siempre se conserva la fuente oficial, la fecha de descarga y la definición de cada indicador.
- Se separan los datos recientes de las fotografías estructurales para no sacar conclusiones equivocadas.
- Se registran revisiones: una cifra inicial puede actualizarse cuando el organismo publique información más completa.
- La automatización reduce trabajo manual, pero no sustituye la validación económica de los resultados.
