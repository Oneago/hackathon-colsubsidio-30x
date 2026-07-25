# App móvil — Supernumerario (Flutter, Android)

App de campo para el conteo físico. **Nunca recibe la cantidad del ERP** (consume solo
endpoints `/movil`). TTS offline (descarga los `.mp3` pre-generados); STT nativo es-CO.

## Requisitos
- Flutter SDK (Dart 3.11+), Android SDK + un emulador o tablet/celular Android.
- Nada más: por defecto la app consume el backend desplegado en
  `https://syncrologix-api.macondo.page`. Solo si quieres trabajar contra un backend local
  necesitas `docker compose up` en la raíz del repo (la API escucha en `0.0.0.0`).

## Ejecutar

Contra el servidor desplegado (por defecto, no requiere flags):

```bash
cd mobile
flutter pub get
flutter run
```

Contra un backend local, sobreescribiendo la URL base con `--dart-define`:

```bash
# Emulador de Android:
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000

# Dispositivo físico en la misma red (usa la IP LAN del equipo anfitrión):
flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000
```

> Para conocer la IP LAN del anfitrión: `ipconfig getifaddr en0` (macOS) o `hostname -I` (Linux).

Construir el APK (apunta al servidor desplegado):
```bash
flutter build apk
```

## Login de prueba
1. En la web, el admin crea un **supernumerario** (rol supernumerario, 1 bodega) y le asigna un listado.
2. En la app, ingresa con esa **cédula + contraseña**.

## Flujo
1. Login (cédula + contraseña) → descarga el listado asignado **sin cantidades ERP** + los `.mp3`.
2. Selección por **escaneo** (código de barras) o **búsqueda**.
3. Confirmación: reproduce el **audio local** y muestra en grande y alto contraste
   `"Usted contará: <ítem>, en <unidad>. Confirme para continuar."`
4. Dictado de la cantidad por **voz (STT es-CO)**; muestra lo reconocido y pide confirmar.
5. **Fallback:** tras **3 intentos** fallidos se habilita el teclado numérico.
6. Envía el conteo (con método escaneo/búsqueda y entrada voz/manual) → el ítem queda marcado.

## Modo offline total (Post-MVP)
La app opera **sin conexión** en bodega:
- El **listado y sus ítems se cachean en SQLite** (`lib/db/local_db.dart`): sobreviven al cierre
  de la app y se muestran sin red. Los `.mp3` ya viven en disco.
- Cada conteo se guarda primero en una **cola local** (`conteo_cola`) y el ítem se marca contado
  al instante (captura offline-first). El envío al servidor es best-effort.
- **Sincronización:** al recuperar conexión (listener `connectivity_plus`) o con el botón de
  sync del AppBar, la cola se drena. La barra superior muestra estado **en línea / sin conexión**
  y un badge con los **pendientes**.
- **Resolución de conflictos** (`resolverSync`, `lib/db/sync_models.dart`): `2xx`→sincronizado;
  `409` (toma cerrada) / `401` / `403`→**conflicto** (se marca y se informa, no se reintenta a ciegas);
  sin red / `5xx`→sigue **pendiente** (se reintenta). Recuento libre: el servidor asigna el
  `intento_num`, vale el último mientras la toma esté abierta.
- **Sesión offline:** el token se persiste; al reabrir la app sin red se restaura la sesión y el
  listado cacheado (el login inicial sí requiere conexión una vez).

## Notas
- **STT offline:** requiere el paquete de idioma **es-CO** descargado en la tablet
  (Ajustes → Google → Voz → Reconocimiento sin conexión). Sin él, el STT no funciona sin red;
  el fallback manual siempre cubre ese caso.
- Permisos declarados: `INTERNET`, `CAMERA` (escaneo), `RECORD_AUDIO` (dictado).
- `usesCleartextTraffic=true` está habilitado únicamente para permitir `http://` contra un backend
  local; contra el servidor desplegado el tráfico va por HTTPS y no hace falta.
- Verificación estática: `flutter analyze` (sin issues) y `flutter test`
  (parser de cantidad, política de conflictos `resolverSync`, cache SQLite con `sqflite_common_ffi`).
