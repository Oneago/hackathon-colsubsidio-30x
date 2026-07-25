/// Configuración. La URL base de la API apunta por defecto al backend desplegado
/// y se puede sobreescribir por `--dart-define` para desarrollo local:
///
///   flutter run                                                     (servidor desplegado)
///   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000     (backend local, emulador)
///   flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000 (backend local, dispositivo físico)
///
/// Siempre sin barra final: las rutas se concatenan ya absolutas (`/movil/...`).
class AppConfig {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://syncrologix-api.oneago.com',
  );
}
