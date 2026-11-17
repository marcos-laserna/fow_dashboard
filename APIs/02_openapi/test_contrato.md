# Caso de uso — OpenAPI como prueba de contrato

OpenAPI no añade una consulta económica nueva: valida que el conector de `01_api_json` sigue hablando el idioma correcto de INEbase.

## Escenario ilustrativo

En Swagger, localizar `DATOS_TABLA` y reproducir esta petición de inflación regional:

```text
GET /wstempus/js/ES/DATOS_TABLA/50913
  ?nult=12
  &tip=A
  &tv=3:74
  &tv=762:304092
  &tv=70:9003
  &tv=70:8999
```

Debe devolver dos series: Asturias y Castilla y León, con el nombre de serie y un array `Data` de observaciones. Comparar el resultado con `../01_api_json/test_ipc.ps1`.

## Qué demuestra

Que, si el INE cambia un parámetro, un nombre de campo o una respuesta, podemos detectarlo antes de que falle una actualización automática del cuadro de mando.
