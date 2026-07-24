/// Modelos del canal móvil. Ninguno incluye la cantidad del ERP (anti-sesgo).
class SesionUsuario {
  final String token;
  final String rol;
  final String nombre;
  final bool mustChangePassword;

  SesionUsuario({
    required this.token,
    required this.rol,
    required this.nombre,
    required this.mustChangePassword,
  });

  factory SesionUsuario.fromJson(Map<String, dynamic> j) => SesionUsuario(
        token: j['access_token'] as String,
        rol: j['rol'] as String,
        nombre: j['nombre'] as String,
        mustChangePassword: (j['must_change_password'] as bool?) ?? false,
      );
}

class MovilItem {
  final int listadoItemId;
  final int itemId;
  final String codigoBarras;
  final String descripcion;
  final String unidad;
  final String unidadTexto;
  final String fraseConfirmacion;
  final String? audioUrl;
  bool contado;
  String? audioLocalPath;

  MovilItem({
    required this.listadoItemId,
    required this.itemId,
    required this.codigoBarras,
    required this.descripcion,
    required this.unidad,
    required this.unidadTexto,
    required this.fraseConfirmacion,
    required this.audioUrl,
    required this.contado,
    this.audioLocalPath,
  });

  factory MovilItem.fromJson(Map<String, dynamic> j) => MovilItem(
        listadoItemId: j['listado_item_id'] as int,
        itemId: j['item_id'] as int,
        codigoBarras: j['codigo_barras'] as String,
        descripcion: j['descripcion'] as String,
        unidad: j['unidad'] as String,
        unidadTexto: j['unidad_texto'] as String,
        fraseConfirmacion: j['frase_confirmacion'] as String,
        audioUrl: j['audio_url'] as String?,
        contado: (j['contado'] as bool?) ?? false,
      );
}

class MovilListado {
  final int listadoId;
  final int tomaId;
  final int bodegaId;
  final String bodegaNombre;
  final List<MovilItem> items;

  MovilListado({
    required this.listadoId,
    required this.tomaId,
    required this.bodegaId,
    required this.bodegaNombre,
    required this.items,
  });

  factory MovilListado.fromJson(Map<String, dynamic> j) => MovilListado(
        listadoId: j['listado_id'] as int,
        tomaId: j['toma_id'] as int,
        bodegaId: j['bodega_id'] as int,
        bodegaNombre: j['bodega_nombre'] as String,
        items: (j['items'] as List<dynamic>)
            .map((e) => MovilItem.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}
