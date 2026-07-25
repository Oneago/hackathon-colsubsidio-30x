/// Da formato a una cantidad para mostrarla en pantalla: coma decimal, sin
/// ceros de cola. Ej.: 5.0 -> "5", 5.483 -> "5,483", 5.9 -> "5,9".
///
/// USAR SOLO PARA PRESENTACIÓN. El `double` crudo (`_cantidad`) debe seguir
/// viajando intacto al backend y a SQLite — nunca pasar el resultado de esta
/// función a `_guardar()` ni a las columnas de sincronización.
String formatearCantidad(double valor, {int decimales = 3}) {
  var texto = valor.toStringAsFixed(decimales);
  // Evita el "-0" engañoso (ej. una diferencia local muy pequeña y negativa).
  if (RegExp(r'^-?0+(\.0+)?$').hasMatch(texto)) {
    texto = texto.replaceFirst('-', '');
  }
  if (texto.contains('.')) {
    texto = texto.replaceFirst(RegExp(r'0+$'), '');
    texto = texto.replaceFirst(RegExp(r'\.$'), '');
  }
  return texto.replaceFirst('.', ',');
}
