# Caso de uso — panel macro para nowcasting de empleo

## Pregunta

**¿Los indicadores más recientes describen expansión o debilitamiento de la actividad y qué podría anticipar para el empleo?**

## Cesta mínima de extracción

| Señal | Código SDMX | Fuente | Uso analítico |
| --- | --- | --- | --- |
| PIB / cuentas nacionales | NAG | INE | Actividad agregada trimestral |
| Producción industrial | IND | INE | Señal mensual de industria |
| Empleo y desempleo | EMP, UEM | INE | Variable objetivo y contraste |
| Costes laborales | WOE | INE | Presión de costes y contratación |
| IPC | CPI | INE | Deflactar y medir poder adquisitivo |
| Balanza comercial | MET | AEAT | Demanda externa |
| Tipos de interés mensuales | INR | BdE | Condiciones financieras |

## Prueba de aceptación

1. Resolver el *dataflow* y sus dimensiones desde el catálogo SDMX vigente; no adivinar códigos de serie.
2. Descargar una ventana de 24 períodos por serie y conservar `fuente`, `unidad`, `frecuencia`, ajuste estacional y fecha de descarga.
3. Comprobar que no hay períodos duplicados y que las frecuencias se tratan por separado: no sumar datos mensuales y trimestrales.
4. Construir una tabla larga y una tabla mensual de señales, aplicando una regla explícita de conversión para las series trimestrales.
5. Contrastar CPI, EMP y UEM con su publicación INE cuando exista solape; las diferencias de *vintage* se documentan, no se sobrescriben.

## Resultado que ilustra

Una lectura conjunta, no causal: producción y PIB aportan actividad; comercio y tipos, contexto externo/financiero; costes e inflación, presión sobre hogares y empresas; empleo y paro, la respuesta laboral observada.
