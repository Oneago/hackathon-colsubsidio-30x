import '../api_client.dart';
import '../db/local_db.dart';
import '../db/sync_models.dart';

/// Resultado de una pasada de sincronización.
class SyncResultado {
  final int sincronizados;
  final int conflictos;
  final int pendientes;
  const SyncResultado(this.sincronizados, this.conflictos, this.pendientes);
}

/// Drena la cola de conteos: intenta enviar cada pendiente y aplica la política
/// de conflictos (`resolverSync`). No borra los conflictos: quedan visibles para
/// que el supervisor decida (p. ej. si la toma se cerró antes de sincronizar).
class SyncService {
  final ApiClient api;
  final LocalDb db;

  SyncService(this.api, this.db);

  Future<SyncResultado> sincronizar() async {
    final pendientes = await db.pendientes();
    var ok = 0, conflicto = 0, sigue = 0;

    for (final c in pendientes) {
      final status = await api.enviarConteoSync(
        listadoItemId: c.listadoItemId,
        cantidad: c.cantidad,
        metodo: c.metodo,
        entrada: c.entrada,
      );
      final nuevo = resolverSync(status);
      switch (nuevo) {
        case SyncStatus.sincronizado:
          ok++;
          await db.actualizarEstado(c.localId!, nuevo);
        case SyncStatus.conflicto:
          conflicto++;
          await db.actualizarEstado(c.localId!, nuevo, error: 'HTTP $status');
        case SyncStatus.pendiente:
          sigue++; // sin red o 5xx: se reintenta luego
      }
    }
    return SyncResultado(ok, conflicto, sigue);
  }
}
