/// Estados de sincronización de un conteo registrado offline.
enum SyncStatus { pendiente, sincronizado, conflicto }

SyncStatus syncStatusFrom(String s) => SyncStatus.values.firstWhere(
      (e) => e.name == s,
      orElse: () => SyncStatus.pendiente,
    );

/// Conteo capturado en el dispositivo. Vive en SQLite hasta sincronizarse.
class ConteoPendiente {
  final int? localId;
  final int listadoItemId;
  final num cantidad;
  final String metodo; // 'escaneo' | 'busqueda'
  final String entrada; // 'voz' | 'manual'
  final String creadoEn; // ISO-8601 local
  SyncStatus estado;
  String? error;

  ConteoPendiente({
    this.localId,
    required this.listadoItemId,
    required this.cantidad,
    required this.metodo,
    required this.entrada,
    required this.creadoEn,
    this.estado = SyncStatus.pendiente,
    this.error,
  });

  Map<String, Object?> toMap() => {
        if (localId != null) 'local_id': localId,
        'listado_item_id': listadoItemId,
        'cantidad': cantidad,
        'metodo': metodo,
        'entrada': entrada,
        'creado_en': creadoEn,
        'estado': estado.name,
        'error': error,
      };

  factory ConteoPendiente.fromMap(Map<String, Object?> m) => ConteoPendiente(
        localId: m['local_id'] as int?,
        listadoItemId: m['listado_item_id'] as int,
        cantidad: m['cantidad'] as num,
        metodo: m['metodo'] as String,
        entrada: m['entrada'] as String,
        creadoEn: m['creado_en'] as String,
        estado: syncStatusFrom(m['estado'] as String? ?? 'pendiente'),
        error: m['error'] as String?,
      );
}

/// Resultado esperado al intentar sincronizar un conteo, según la respuesta del
/// servidor. Lógica PURA (sin red) para poder probarla en unit tests.
///
/// Política de conflictos (plan): recuento libre mientras la toma esté ABIERTA;
/// vale el último. Por eso:
/// - 2xx  → sincronizado (el server acepta y asigna el intento).
/// - 409  → conflicto NO recuperable (toma cerrada): se marca y se informa; no se reintenta.
/// - 401/403 → conflicto (sesión/permiso): requiere reingreso; no se reintenta a ciegas.
/// - error de red / 5xx / null → sigue PENDIENTE (se reintentará al reconectar).
SyncStatus resolverSync(int? statusCode) {
  if (statusCode == null) return SyncStatus.pendiente; // sin conexión / timeout
  if (statusCode >= 200 && statusCode < 300) return SyncStatus.sincronizado;
  if (statusCode == 409 || statusCode == 401 || statusCode == 403) {
    return SyncStatus.conflicto;
  }
  return SyncStatus.pendiente; // 5xx u otros → reintentar
}
