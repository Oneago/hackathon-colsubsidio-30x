import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';
import 'models.dart';

class ApiException implements Exception {
  final int status;
  final String message;
  ApiException(this.status, this.message);
  @override
  String toString() => message;
}

/// Cliente HTTP del canal móvil. Consume únicamente endpoints /movil (sin ERP).
class ApiClient {
  String? token;

  Uri _u(String path) => Uri.parse('${AppConfig.apiBaseUrl}$path');

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  Future<SesionUsuario> loginMovil(String cedula, String password) async {
    final res = await http.post(
      _u('/auth/login/movil'),
      headers: _headers,
      body: jsonEncode({'cedula': cedula, 'password': password}),
    );
    _check(res);
    final sesion = SesionUsuario.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
    token = sesion.token;
    return sesion;
  }

  Future<MovilListado> miListado() async {
    final res = await http.get(_u('/movil/mi-listado'), headers: _headers);
    _check(res);
    return MovilListado.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<void> registrarConteo({
    required int listadoItemId,
    required num cantidad,
    required String metodo,
    required String entrada,
  }) async {
    final res = await http.post(
      _u('/movil/conteos'),
      headers: _headers,
      body: jsonEncode({
        'listado_item_id': listadoItemId,
        'cantidad_contada': cantidad,
        'metodo': metodo,
        'entrada': entrada,
      }),
    );
    _check(res);
  }

  /// Intenta enviar un conteo y devuelve el código HTTP; `null` si no hubo red
  /// (timeout / sin conexión). No lanza: lo usa la cola de sincronización offline.
  Future<int?> enviarConteoSync({
    required int listadoItemId,
    required num cantidad,
    required String metodo,
    required String entrada,
  }) async {
    try {
      final res = await http
          .post(
            _u('/movil/conteos'),
            headers: _headers,
            body: jsonEncode({
              'listado_item_id': listadoItemId,
              'cantidad_contada': cantidad,
              'metodo': metodo,
              'entrada': entrada,
            }),
          )
          .timeout(const Duration(seconds: 10));
      return res.statusCode;
    } catch (_) {
      return null; // sin conexión: permanece pendiente
    }
  }

  void _check(http.Response res) {
    if (res.statusCode >= 400) {
      var msg = 'Error ${res.statusCode}';
      try {
        final j = jsonDecode(res.body);
        if (j is Map && j['detail'] is String) msg = j['detail'] as String;
      } catch (_) {
        // respuesta sin cuerpo JSON
      }
      throw ApiException(res.statusCode, msg);
    }
  }
}
