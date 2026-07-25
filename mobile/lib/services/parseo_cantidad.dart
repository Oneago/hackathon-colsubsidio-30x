/// Extrae una cantidad numérica de un texto reconocido por voz (es-CO).
/// Devuelve null si no logra interpretar un número.
///
/// Une en una sola pasada dígitos, palabras y multiplicadores ("mil") porque
/// ElevenLabs puede transcribir el mismo dictado de tres formas distintas
/// ("treinta y tres mil", "33.000" con separador de miles es-CO, o la híbrida
/// "33 mil"): tratarlas como ramas separadas donde solo una "gana" hace que
/// las otras dos se interpreten mal (p. ej. "33.000" leído como decimal 33.0).
double? parseCantidad(String texto) {
  final limpio = _sinAcentos(texto.toLowerCase()).trim();
  if (limpio.isEmpty) return null;

  final tokens = limpio
      .replaceAll(' y ', ' ')
      .split(RegExp(r'\s+'))
      .map((t) => t.replaceAll(RegExp(r'^[^\w]+|[^\w]+$'), ''))
      .where((t) => t.isNotEmpty)
      .toList();

  num total = 0;
  num actual = 0;
  var reconocio = false;

  for (final t in tokens) {
    final digitos = _parseGrupoDigitos(t);
    if (digitos != null) {
      actual += digitos;
      reconocio = true;
      continue;
    }
    final palabra = _palabras[t];
    if (palabra != null) {
      actual += palabra;
      reconocio = true;
      continue;
    }
    final multiplicador = _multiplicadores[t];
    if (multiplicador != null) {
      total += (actual == 0 ? 1 : actual) * multiplicador;
      actual = 0;
      reconocio = true;
      continue;
    }
    // Token no reconocido (ruido de la frase o de la transcripción): se ignora.
  }

  if (!reconocio) return null;
  return (total + actual).toDouble();
}

/// Interpreta un token puramente numérico, resolviendo si "." o "," es
/// separador de miles o marca decimal (convención es-CO).
double? _parseGrupoDigitos(String s) {
  if (!RegExp(r'^\d+([.,]\d+)*$').hasMatch(s)) return null;

  final tieneComa = s.contains(',');
  final tienePunto = s.contains('.');
  if (!tieneComa && !tienePunto) return double.tryParse(s);

  if (tieneComa && tienePunto) {
    final decimalEsComa = s.lastIndexOf(',') > s.lastIndexOf('.');
    final sepMiles = decimalEsComa ? '.' : ',';
    final sepDecimal = decimalEsComa ? ',' : '.';
    return double.tryParse(s.replaceAll(sepMiles, '').replaceAll(sepDecimal, '.'));
  }

  final sep = tieneComa ? ',' : '.';
  final partes = s.split(sep);
  // Un solo separador: es de miles si deja exactamente 3 dígitos detrás (y
  // por tanto también si hay más de un grupo, ej. "1.234.567"); si no, decimal.
  final esDecimal = partes.length == 2 && partes.last.length != 3;
  return double.tryParse(esDecimal ? s.replaceAll(sep, '.') : partes.join());
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
  'doscientos': 200, 'doscientas': 200, 'trescientos': 300, 'trescientas': 300,
  'cuatrocientos': 400, 'cuatrocientas': 400, 'quinientos': 500, 'quinientas': 500,
  'seiscientos': 600, 'seiscientas': 600, 'setecientos': 700, 'setecientas': 700,
  'ochocientos': 800, 'ochocientas': 800, 'novecientos': 900, 'novecientas': 900,
};

const Map<String, int> _multiplicadores = {'mil': 1000};
