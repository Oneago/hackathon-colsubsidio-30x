/// Configuración. La URL base de la API se inyecta por --dart-define, nunca
/// se escribe a mano en el código:
///
///   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000    (emulador)
///   flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000 (dispositivo físico, IP LAN)
class AppConfig {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );
}
