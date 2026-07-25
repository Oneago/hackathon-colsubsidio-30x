// Pruebas unitarias del formato de cantidad para presentación.
import 'package:flutter_test/flutter_test.dart';
import 'package:inventario_movil/services/formato_cantidad.dart';

void main() {
  group('formatearCantidad', () {
    test('recorta ceros de cola', () {
      expect(formatearCantidad(10.0), '10');
      expect(formatearCantidad(1547.0), '1547');
      expect(formatearCantidad(0.0), '0');
    });

    test('conserva decimales significativos', () {
      expect(formatearCantidad(5.483), '5,483');
      expect(formatearCantidad(5.9), '5,9');
      expect(formatearCantidad(5.48), '5,48');
    });

    test('usa coma en vez de punto', () {
      expect(formatearCantidad(5.483).contains(','), isTrue);
      expect(formatearCantidad(5.483).contains('.'), isFalse);
    });

    test('maneja negativos', () {
      expect(formatearCantidad(-3.0), '-3');
    });

    test('evita el "-0" engañoso', () {
      expect(formatearCantidad(-0.04, decimales: 1), '0');
    });

    test('admite una escala distinta a la de 3 decimales por defecto', () {
      expect(formatearCantidad(33.333333, decimales: 1), '33,3');
    });
  });
}
