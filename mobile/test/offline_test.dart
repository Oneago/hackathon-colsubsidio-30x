import 'package:flutter_test/flutter_test.dart';
import 'package:inventario_movil/db/local_db.dart';
import 'package:inventario_movil/db/sync_models.dart';
import 'package:inventario_movil/models.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  setUpAll(() {
    sqfliteFfiInit();
  });

  group('resolverSync (política de conflictos)', () {
    test('2xx → sincronizado', () {
      expect(resolverSync(200), SyncStatus.sincronizado);
      expect(resolverSync(201), SyncStatus.sincronizado);
    });
    test('409/401/403 → conflicto (no reintentar)', () {
      expect(resolverSync(409), SyncStatus.conflicto); // toma cerrada
      expect(resolverSync(401), SyncStatus.conflicto);
      expect(resolverSync(403), SyncStatus.conflicto);
    });
    test('null (sin red) o 5xx → sigue pendiente', () {
      expect(resolverSync(null), SyncStatus.pendiente);
      expect(resolverSync(503), SyncStatus.pendiente);
    });
  });

  group('LocalDb (SQLite en memoria)', () {
    late LocalDb db;

    setUp(() async {
      db = LocalDb();
      await db.open(factory: databaseFactoryFfi, path: inMemoryDatabasePath);
    });

    test('cachea y recupera el listado', () async {
      final listado = MovilListado(
        listadoId: 1, tomaId: 2, bodegaId: 3, bodegaNombre: 'Bodega X',
        items: [
          MovilItem(
            listadoItemId: 10, itemId: 100, codigoBarras: '123',
            descripcion: 'ACEITE', unidad: 'litro', unidadTexto: 'litros',
            fraseConfirmacion: 'Usted contará: ACEITE, en litros. Confirme para continuar.',
            audioUrl: '/audio/x.mp3', contado: false,
          ),
        ],
      );
      await db.guardarListado(listado);
      final cargado = await db.cargarListado();
      expect(cargado, isNotNull);
      expect(cargado!.bodegaNombre, 'Bodega X');
      expect(cargado.items.single.descripcion, 'ACEITE');
    });

    test('encola conteos y cuenta pendientes', () async {
      await db.encolarConteo(ConteoPendiente(
        listadoItemId: 10, cantidad: 5, metodo: 'escaneo', entrada: 'voz',
        creadoEn: DateTime.now().toIso8601String(),
      ));
      expect(await db.contarPendientes(), 1);

      final p = (await db.pendientes()).single;
      await db.actualizarEstado(p.localId!, SyncStatus.sincronizado);
      expect(await db.contarPendientes(), 0);
    });

    test('marca ítem como contado en el cache', () async {
      await db.guardarListado(MovilListado(
        listadoId: 1, tomaId: 1, bodegaId: 1, bodegaNombre: 'B',
        items: [
          MovilItem(
            listadoItemId: 10, itemId: 1, codigoBarras: '1', descripcion: 'A',
            unidad: 'unidad', unidadTexto: 'unidades', fraseConfirmacion: 'x',
            audioUrl: null, contado: false,
          ),
        ],
      ));
      await db.marcarItemContado(10);
      final cargado = await db.cargarListado();
      expect(cargado!.items.single.contado, isTrue);
    });
  });
}
