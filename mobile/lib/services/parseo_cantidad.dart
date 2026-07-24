/// Extrae una cantidad numérica de un texto reconocido por voz (es-CO).
/// Devuelve null si no logra interpretar un número.
double? parseCantidad(String texto) {
  final limpio = _sinAcentos(texto.toLowerCase()).trim();
  if (limpio.isEmpty) return null;

  // 1) Dígitos explícitos ("7", "3.5", "3,5").
  final match = RegExp(r'\d+([.,]\d+)?').firstMatch(limpio);
  if (match != null) {
    return double.tryParse(match.group(0)!.replaceAll(',', '.'));
  }

  // 2) Números en palabras (0–99 + cien), incluyendo compuestos ("treinta y cinco").
  final tokens = limpio.replaceAll(' y ', ' ').split(RegExp(r'\s+'));
  int? suma;
  for (final t in tokens) {
    final v = _palabras[t];
    if (v != null) suma = (suma ?? 0) + v;
  }
  return suma?.toDouble();
}

String _sinAcentos(String s) => s
    .replaceAll('á', 'a')
    .replaceAll('é', 'e')
    .replaceAll('í', 'i')
    .replaceAll('ó', 'o')
    .replaceAll('ú', 'u')
    .replaceAll('ü', 'u');

const Map<String, int> _palabras = {
  'cero': 0, 'un': 1, 'uno': 1, 'una': 1, 'dos': 2, 'tres': 3, 'cuatro': 4,
  'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10,
  'once': 11, 'doce': 12, 'trece': 13, 'catorce': 14, 'quince': 15,
  'dieciseis': 16, 'diecisiete': 17, 'dieciocho': 18, 'diecinueve': 19,
  'veinte': 20, 'veintiuno': 21, 'veintiuna': 21, 'veintidos': 22,
  'veintitres': 23, 'veinticuatro': 24, 'veinticinco': 25, 'veintiseis': 26,
  'veintisiete': 27, 'veintiocho': 28, 'veintinueve': 29,
  'treinta': 30, 'cuarenta': 40, 'cincuenta': 50, 'sesenta': 60,
  'setenta': 70, 'ochenta': 80, 'noventa': 90, 'cien': 100, 'ciento': 100,
};
