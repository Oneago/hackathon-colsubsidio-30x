import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';
import 'db/local_db.dart';
import 'db/sync_models.dart';
import 'models.dart';
import 'services/audio_service.dart';
import 'services/sync_service.dart';

/// Estado global. OFFLINE-FIRST: los conteos se guardan en SQLite y se
/// sincronizan cuando hay red; el listado se cachea para operar sin conexión.
class AppState extends ChangeNotifier {
  final ApiClient api = ApiClient();
  final AudioService audio = AudioService();
  final LocalDb db = LocalDb();
  late final SyncService sync = SyncService(api, db);
  final Connectivity _connectivity = Connectivity();
  StreamSubscription<List<ConnectivityResult>>? _connSub;

  SesionUsuario? sesion;
  MovilListado? listado;
  String? error;
  bool cargando = false;
  bool inicializando = true;
  bool online = true;
  bool sinListadoAsignado = false;
  int pendientes = 0;

  bool get autenticado => sesion != null;
  int get totalItems => listado?.items.length ?? 0;
  int get contados => listado?.items.where((i) => i.contado).length ?? 0;

  AppState() {
    _init();
  }

  /// Restaura la sesión y el listado desde el almacenamiento local (sin exigir
  /// red). Si hay conexión, refresca desde el servidor y drena la cola.
  Future<void> _init() async {
    _connSub = _connectivity.onConnectivityChanged.listen(_onConnectivity);
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('token');
    if (token != null) {
      api.token = token;
      sesion = SesionUsuario(
        token: token,
        rol: prefs.getString('rol') ?? 'supernumerario',
        nombre: prefs.getString('nombre') ?? '',
        mustChangePassword: false,
      );
      listado = await db.cargarListado(); // offline
      pendientes = await db.contarPendientes();
      online = await _hayRed();
      if (online) {
        await _sincronizarYRefrescar();
      }
    }
    inicializando = false;
    notifyListeners();
  }

  Future<bool> _hayRed() async {
    final r = await _connectivity.checkConnectivity();
    return !r.contains(ConnectivityResult.none);
  }

  Future<void> _onConnectivity(List<ConnectivityResult> r) async {
    online = !r.contains(ConnectivityResult.none);
    notifyListeners();
    if (online && autenticado) {
      await _sincronizarYRefrescar();
    }
  }

  Future<bool> login(String cedula, String password) async {
    cargando = true;
    error = null;
    notifyListeners();
    try {
      sesion = await api.loginMovil(cedula, password);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('token', sesion!.token);
      await prefs.setString('rol', sesion!.rol);
      await prefs.setString('nombre', sesion!.nombre);
      await _sincronizarYRefrescar();
      cargando = false;
      notifyListeners();
      return true;
    } on ApiException catch (e) {
      cargando = false;
      error = e.message;
      notifyListeners();
      return false;
    } catch (_) {
      cargando = false;
      error = 'No se pudo conectar con el servidor';
      notifyListeners();
      return false;
    }
  }

  /// Drena la cola y luego refresca el listado desde el servidor (si hay red).
  Future<void> _sincronizarYRefrescar() async {
    try {
      await sync.sincronizar();
      final l = await api.miListado();
      await audio.descargarAudios(l.items);
      // Conserva la marca local de ítems con conteos aún no confirmados.
      final pend = await db.pendientes();
      final conf = await db.conflictos();
      final marcados = {...pend, ...conf}.map((c) => c.listadoItemId).toSet();
      for (final it in l.items) {
        if (marcados.contains(it.listadoItemId)) it.contado = true;
      }
      await db.guardarListado(l);
      listado = l;
      pendientes = await db.contarPendientes();
      sinListadoAsignado = false;
    } on ApiException catch (e) {
      // El servidor respondió (hay red): "sin listado asignado" no es una
      // falla de conectividad, es un estado válido a la espera de asignación.
      if (e.status == 404) {
        sinListadoAsignado = true;
        online = true;
      } else {
        online = false;
      }
    } catch (_) {
      // sin red o error transitorio: se mantiene el cache local
      online = false;
    }
    notifyListeners();
  }

  Future<void> sincronizarManual() async {
    online = await _hayRed();
    if (online) await _sincronizarYRefrescar();
  }

  /// Registra un conteo OFFLINE-FIRST: lo encola en SQLite, marca el ítem como
  /// contado localmente y trata de enviarlo de inmediato (si hay red).
  Future<void> registrarConteo(
    MovilItem item, {
    required num cantidad,
    required String metodo,
    required String entrada,
  }) async {
    await db.encolarConteo(ConteoPendiente(
      listadoItemId: item.listadoItemId,
      cantidad: cantidad,
      metodo: metodo,
      entrada: entrada,
      creadoEn: DateTime.now().toIso8601String(),
    ));
    item.contado = true;
    await db.marcarItemContado(item.listadoItemId);
    pendientes = await db.contarPendientes();
    notifyListeners();

    // Intento inmediato (best-effort); si falla queda en la cola.
    await sync.sincronizar();
    pendientes = await db.contarPendientes();
    notifyListeners();
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('token');
    await prefs.remove('rol');
    await prefs.remove('nombre');
    await db.limpiar();
    sesion = null;
    listado = null;
    pendientes = 0;
    api.token = null;
    notifyListeners();
  }

  @override
  void dispose() {
    _connSub?.cancel();
    super.dispose();
  }
}
