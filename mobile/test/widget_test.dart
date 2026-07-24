// Pruebas unitarias del parseo de cantidad (voz → número).
import 'package:flutter_test/flutter_test.dart';
import 'package:inventario_movil/services/parseo_cantidad.dart';

void main() {
  group('parseCantidad', () {
    test('reconoce dígitos', () {
      expect(parseCantidad('7'), 7);
      expect(parseCantidad('son 12 unidades'), 12);
    });

    test('reconoce decimales con coma o punto', () {
      expect(parseCantidad('3,5'), 3.5);
      expect(parseCantidad('10.25'), 10.25);
    });

    test('reconoce palabras en español', () {
      expect(parseCantidad('siete'), 7);
      expect(parseCantidad('veinte'), 20);
    });

    test('reconoce números compuestos y con acentos', () {
      expect(parseCantidad('veinticinco'), 25);
      expect(parseCantidad('treinta y cinco'), 35);
      expect(parseCantidad('veintitrés'), 23);
      expect(parseCantidad('dieciséis'), 16);
    });

    test('devuelve null si no hay número', () {
      expect(parseCantidad('no sé'), isNull);
      expect(parseCantidad(''), isNull);
    });
  });
}
