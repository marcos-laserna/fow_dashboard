# Caso de uso: prototipo R de inflación regional para seguimiento de poder adquisitivo.
# INEapir es un cliente de la API JSON; el dato subyacente es el mismo.
library(ineapir)

ipc <- get_data_table(idTable = 50913, nlast = 12, tip = "A", unnest = TRUE)

# El filtrado se hace sobre etiquetas ya devueltas. En producción se preferiría
# filtrar en la URL/API para minimizar descarga y hacer el proceso más eficiente.
resultado <- subset(
  ipc,
  grepl("Asturias, Principado de|Castilla y León", Nombre) &
    grepl("Índice general. Variación anual", Nombre)
)

stopifnot(nrow(resultado) > 0)
print(resultado[, c("COD", "Nombre", "Fecha", "Valor")])
