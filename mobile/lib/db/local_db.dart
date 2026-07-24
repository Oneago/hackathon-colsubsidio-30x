import 'package:sqflite/sqflite.dart';

import '../models.dart';
import 'sync_models.dart';

/// Base de datos local (SQLite) para operación OFFLINE TOTAL:
/// - cachea el listado asignado y sus ítems (sobreviven cierre de app / sin red),
/// - guarda los conteos en una cola hasta que puedan sincronizarse.
class LocalDb {
  Database? _db;

  /// Permite inyectar un `databaseFactory`/ruta en pruebas (sqflite_common_ffi).
  Future<Database> open({DatabaseFactory? factory, String path = 'inventario.db'}) async {
    if (_db != null) return _db!;
    final f = factory ?? databaseFactory;
    _db = await f.openDatabase(
      path,
      options: OpenDatabaseOptions(version: 1, onCreate: _onCreate),
    );
    return _db!;
  }

  Future<void> _onCreate(Database db, int version) async {
    await db.execute('''
      CREATE TABLE listado_cache (
        id INTEGER PRIMARY KEY,
        toma_id INTEGER NOT NULL,
        bodega_id INTEGER NOT NULL,
        bodega_nombre TEXT NOT NULL
      )''');
    await db.execute('''
      CREATE TABLE item_cache (
        listado_item_id INTEGER PRIMARY KEY,
        item_id INTEGER NOT NULL,
        codigo_barras TEXT NOT NULL,
        descripcion TEXT NOT NULL,
        unidad TEXT NOT NULL,
        unidad_texto TEXT NOT NULL,
        frase_confirmacion TEXT NOT NULL,
        audio_url TEXT,
        audio_local_path TEXT,
        contado INTEGER NOT NULL DEFAULT 0
      )''');
    await db.execute('''
      CREATE TABLE conteo_cola (
        local_id INTEGER PRIMARY KEY AUTOINCREMENT,
        listado_item_id INTEGER NOT NULL,
        cantidad REAL NOT NULL,
        metodo TEXT NOT NULL,
        entrada TEXT NOT NULL,
        creado_en TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'pendiente',
        error TEXT
      )''');
  }

  // ── Cache del listado ──────────────────────────────────────
  Future<void> guardarListado(MovilListado l) async {
    final db = await open();
    await db.transaction((txn) async {
      await txn.delete('listado_cache');
      await txn.delete('item_cache');
      await txn.insert('listado_cache', {
        'id': l.listadoId,
        'toma_id': l.tomaId,
        'bodega_id': l.bodegaId,
        'bodega_nombre': l.bodegaNombre,
      });
      for (final it in l.items) {
        await txn.insert('item_cache', {
          'listado_item_id': it.listadoItemId,
          'item_id': it.itemId,
          'codigo_barras': it.codigoBarras,
          'descripcion': it.descripcion,
          'unidad': it.unidad,
          'unidad_texto': it.unidadTexto,
          'frase_confirmacion': it.fraseConfirmacion,
          'audio_url': it.audioUrl,
          'audio_local_path': it.audioLocalPath,
          'contado': it.contado ? 1 : 0,
        });
      }
    });
  }

  Future<MovilListado?> cargarListado() async {
    final db = await open();
    final cab = await db.query('listado_cache', limit: 1);
    if (cab.isEmpty) return null;
    final c = cab.first;
    final rows = await db.query('item_cache', orderBy: 'descripcion');
    final items = rows
        .map((r) => MovilItem(
              listadoItemId: r['listado_item_id'] as int,
              itemId: r['item_id'] as int,
              codigoBarras: r['codigo_barras'] as String,
              descripcion: r['descripcion'] as String,
              unidad: r['unidad'] as String,
              unidadTexto: r['unidad_texto'] as String,
              fraseConfirmacion: r['frase_confirmacion'] as String,
              audioUrl: r['audio_url'] as String?,
              contado: (r['contado'] as int) == 1,
              audioLocalPath: r['audio_local_path'] as String?,
            ))
        .toList();
    return MovilListado(
      listadoId: c['id'] as int,
      tomaId: c['toma_id'] as int,
      bodegaId: c['bodega_id'] as int,
      bodegaNombre: c['bodega_nombre'] as String,
      items: items,
    );
  }

  Future<void> marcarItemContado(int listadoItemId) async {
    final db = await open();
    await db.update('item_cache', {'contado': 1},
        where: 'listado_item_id = ?', whereArgs: [listadoItemId]);
  }

  // ── Cola de conteos ────────────────────────────────────────
  Future<int> encolarConteo(ConteoPendiente c) async {
    final db = await open();
    return db.insert('conteo_cola', c.toMap());
  }

  Future<List<ConteoPendiente>> pendientes() async {
    final db = await open();
    final rows = await db.query('conteo_cola',
        where: 'estado = ?', whereArgs: [SyncStatus.pendiente.name], orderBy: 'local_id');
    return rows.map(ConteoPendiente.fromMap).toList();
  }

  Future<int> contarPendientes() async {
    final db = await open();
    final r = await db.rawQuery(
        "SELECT COUNT(*) c FROM conteo_cola WHERE estado = 'pendiente'");
    return Sqflite.firstIntValue(r) ?? 0;
  }

  Future<List<ConteoPendiente>> conflictos() async {
    final db = await open();
    final rows = await db.query('conteo_cola',
        where: 'estado = ?', whereArgs: [SyncStatus.conflicto.name]);
    return rows.map(ConteoPendiente.fromMap).toList();
  }

  Future<void> actualizarEstado(int localId, SyncStatus estado, {String? error}) async {
    final db = await open();
    await db.update('conteo_cola', {'estado': estado.name, 'error': error},
        where: 'local_id = ?', whereArgs: [localId]);
  }

  Future<void> limpiar() async {
    final db = await open();
    await db.delete('listado_cache');
    await db.delete('item_cache');
    await db.delete('conteo_cola');
  }
}
