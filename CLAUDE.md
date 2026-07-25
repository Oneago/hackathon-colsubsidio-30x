# CLAUDE.md

Contexto para agentes que trabajen en este repositorio. Léelo antes de escribir código.

## Qué es esto

Sistema de **toma física de inventario** para bodegas de Hoteles Colsubsidio. Resuelve el
**Reto 4 (Hotelería)** del Hackathon Colsubsidio × 30X (Bogotá, 22–26 de julio de 2026).

El problema: la cadena de captura manual (contar en papel → digitar → revisar) introduce
errores y descuadres. La solución va más allá de "quitar el papel" y ataca el **sesgo de
confirmación**: quien cuenta en campo **nunca ve la cantidad del ERP**, cuenta a ciegas con
apoyo de **voz** y **escaneo**, y el sistema reconcilia después en la consola web.

Estado: MVP completo (Fases 0–7 cerradas, ver `README.md`). Backend desplegado en
`https://syncrologix-api.macondo.page`.

## Arquitectura

| Componente | Stack | Rol |
|---|---|---|
| `api/` | FastAPI + Uvicorn + SQLAlchemy 2 + Alembic + PostgreSQL 16 | Única fuente de verdad. OpenAPI en `/docs` es el contrato para web y móvil. |
| `web/` | React 18 + Vite 5 + TypeScript + Tailwind + componentes estilo shadcn/ui | Consola de administradores y supervisores. |
| `mobile/` | Flutter (Android), offline-first con SQLite | App de campo del supernumerario. |

`api`, `web` y `db` corren en Docker Compose. Flutter **no** se contenedoriza: compila a APK
y corre en el dispositivo o emulador.

## Comandos

```bash
cp .env.example .env    # único paso manual antes del primer arranque
make up                 # levanta el stack en dev (build + hot reload)
make down               # detiene (conserva datos)
make seed               # recarga el dataset (idempotente)
make test               # pytest de la API (BD de test aislada)
make migrate            # alembic upgrade head
make revision m="msg"   # migración autogenerada
make logs               # logs de api (S=db para otro servicio)
make psql               # consola psql
make clean              # ¡DESTRUCTIVO! borra volúmenes
make prod-up            # stack en modo producción
```

Móvil (desde `mobile/`):

```bash
flutter run                                                   # backend desplegado (por defecto)
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000   # backend local, emulador Android
flutter analyze && flutter test
```

URLs en dev: API `http://localhost:8000` · Swagger `/docs` · Web `http://localhost:5173`.
Admin del seed: `ADMIN_CEDULA` / `ADMIN_PASSWORD` del `.env`.

## Invariantes del dominio — no romper

1. **Anti-sesgo.** `Item.cantidad_erp` **jamás** viaja al canal móvil. La separación es de
   **esquema**, no de UI: los modelos Pydantic `Movil*` (`api/app/schemas.py`) simplemente no
   tienen el campo. `api/tests/test_anti_sesgo.py` lo verifica recorriendo el OpenAPI de forma
   transitiva. Si agregas un endpoint bajo `/movil`, no le pongas campos con "erp" en el nombre
   ni referencies esquemas web.
2. **Separación de canales.** El supernumerario **no** entra por web (403 explícito en
   `/auth/login/web`); el supervisor **no** entra por la app móvil (403 en `/auth/login/movil`).
   El admin puede por ambos.
3. **Roles y bodegas.** Supernumerario = exactamente 1 bodega. Supervisor = 1..N. Administrador
   = todas (no se persiste lista). Se valida en `routers/usuarios.py::_resolver_bodegas`.
4. **Alcance por rol.** Admin ve todo; supervisor solo sus bodegas. Se aplica con
   `bodegas.py::bodega_ids_accesibles` / `_verificar_acceso`, reutilizado por tomas, listados y
   reportes.
5. **Concurrencia.** Un solo listado **activo** por (toma, bodega), garantizado por el índice
   único parcial `uq_listado_activo_toma_bodega` (Postgres, `WHERE estado = 'activo'`). La
   segunda asignación recibe 409, no un estado corrupto. Además: a lo sumo una toma abierta por
   bodega.
6. **Recuento libre.** Mientras la toma esté **abierta** se aceptan nuevos conteos del mismo
   ítem; cada uno incrementa `intento_num` y **vale el mayor**. Con la toma cerrada: 409.
7. **Seed idempotente.** `app/seed/seed.py` hace upsert por claves naturales
   (`bodega.id_erp` / `slug`, `item.descripcion_norm`). Correrlo N veces deja el mismo estado.

## Modelo de datos (`api/app/models.py`)

`Bodega` → `Item` (línea de stock; `cantidad_erp`, `codigo_barras`, `descripcion_norm`) ·
`Usuario` (cédula + bcrypt + rol) ↔ `usuario_bodega` (M:N) · `TomaInventario` (abierta/cerrada)
→ `ListadoConteo` (asignación a un supernumerario) → `ListadoItem` → `Conteo` (trazabilidad:
quién, cuándo, `metodo` escaneo/búsqueda, `entrada` voz/manual, `intento_num`) ·
`AudioAsset` (mp3 TTS deduplicado por hash de descripción).

Los enums de dominio son **enums de Postgres** con valores en español (`rol_usuario`,
`unidad_medida`, `estado_toma`, `estado_listado`, `metodo_conteo`, `tipo_entrada`,
`estado_audio`). Cambiarlos exige migración Alembic.

## API — rutas

- `/auth`: `login/web`, `login/movil`, `change-password`, `me`. JWT HS256 vía `HTTPBearer`,
  `sub` = id de usuario. Autorización con `deps.require_roles(...)`.
- `/usuarios` (solo admin), `/bodegas` + `/bodegas/{id}/items` (web, **sí** incluye `cantidad_erp`),
  `/tomas` (abrir/cerrar/listar), `/listados` (asignar).
- `/movil` (solo supernumerario): `mi-listado`, `conteos`.
- `/reportes`: `comparacion` y `comparacion.csv` (Δ absoluto y %, marca de crítico según
  `DIFF_UMBRAL_PCT`, CSV con BOM para Excel).
- `/health` (200/503 según BD) y `/audio` (mp3 estáticos para el móvil).

## Convenciones de código

- **Todo en español**: nombres de tablas, campos, rutas, variables de dominio, docstrings,
  comentarios y mensajes de error de cara al usuario. Mantenlo así.
- Los comentarios explican **por qué** (decisión de diseño, invariante), no qué hace la línea.
  Varios archivos abren con un docstring que fija la regla del módulo: respétalo al editar.
- Sin credenciales en el código: todo por entorno (`app/config.py` con `pydantic-settings`;
  `.env` ignorado, `.env.example` versionado).
- Web: import alias `@/` → `web/src`. Cliente HTTP centralizado en `lib/api.ts` (nunca `fetch`
  suelto en componentes); tipos TS espejo del contrato de la API. Colores solo por tokens CSS
  de `index.css` (derivados de `branding/DESIGN.md`), nunca HEX sueltos.
- Móvil: `AppState` (ChangeNotifier + provider) es el único estado global; la UI no llama al
  `ApiClient` directamente. La URL base solo por `--dart-define=API_BASE_URL`.

## Branding (`branding/DESIGN.md`)

Tres colores de marca: azul `#0067b1` (estructura), amarillo `#ffd000` (acento ~10%), grafito
`#575756` (neutros). Regla WCAG dura: **nunca** texto blanco sobre amarillo ni amarillo sobre
blanco (contraste 1.47); sobre amarillo el texto va en grafito oscuro. Foco visible en azul.
Lee ese archivo antes de tocar estilos.

## App móvil — offline total

Diseñada para bodegas sin señal:

- El listado y sus ítems se cachean en **SQLite** (`lib/db/local_db.dart`); los `.mp3` viven en
  disco (`services/audio_service.dart`).
- Cada conteo entra primero a la cola local `conteo_cola` y el ítem se marca contado al
  instante (**captura offline-first**); el envío es best-effort.
- Sincronización al recuperar red (`connectivity_plus`) o manual desde el AppBar.
- Política de conflictos en `db/sync_models.dart::resolverSync` — lógica **pura** y testeada:
  2xx → sincronizado; 409/401/403 → conflicto (no se reintenta a ciegas); sin red o 5xx →
  sigue pendiente.
- Sesión persistida: al reabrir sin red se restaura token + listado cacheado (el primer login
  sí requiere conexión).
- Flujo de conteo: escaneo o búsqueda → audio + frase en alto contraste → dictado STT `es_CO`
  → tras **3 intentos** fallidos aparece el teclado numérico (`screens/conteo_screen.dart`).
  El parser de voz (`services/parseo_cantidad.dart`) entiende dígitos y palabras es-CO,
  incluidos compuestos ("treinta y cinco").

## Dataset y seed

`dataset/inventory.json` simula la respuesta del ERP: 48 bodegas, 8 ubicaciones de stock,
1405 líneas. Condiciona el diseño:

- **No hay código de barras**: solo `nrArticulo`, ausente en ~18%. El seed genera un código
  sintético `GEN-<sha1[:10]>` estable → 100% escaneable.
- **UoM en inglés** (`Unidad/Kilogram/Liter/Portion`) → se normaliza al enum es-CO.
- `stock` = cantidad ERP → se guarda en `cantidad_erp` (campo anti-sesgo).
- El mapeo stock→bodega es manual y vive en `api/app/seed/bodega_stock_map.json`.

## TTS (ElevenLabs)

`services/tts.py` sintetiza **on-demand al crear un listado** (BackgroundTask), deduplicando
por descripción normalizada y cacheando para siempre en el volumen `audio_store`. Sin API key
degrada con gracia a un mp3 de silencio, así que el flujo sigue siendo demostrable. Es
idempotente: no re-sintetiza lo ya generado (no quema créditos).

## Pruebas

- API: `make test` → pytest contra una BD **dedicada** `<POSTGRES_DB>_test` que se crea al
  vuelo con `create_all` (no toca la base de demo ni las migraciones). Cubre flujo E2E,
  contrato anti-sesgo, seguridad/permisos y reportes.
- Móvil: `flutter test` (parser de cantidad, `resolverSync`, cache SQLite con
  `sqflite_common_ffi`) y `flutter analyze`.

## Entornos y despliegue

- `compose.yaml` — base agnóstica. `compose.override.yaml` — dev (bind mounts, hot reload,
  puertos publicados), se fusiona solo con `docker compose up`. `compose.prod.yaml` — prod
  (Uvicorn sin `--reload`, web como build estático servido por Nginx con SPA fallback).
- `compose.dokploy.yaml` — despliegue real con Traefik + TLS. **Autocontenido a propósito**
  (Dokploy ejecuta un único archivo): no usa el patrón base+override, y ningún servicio publica
  puertos. Si cambias `compose.yaml`, revisa si el cambio también aplica aquí.
- Dockerfiles multi-stage; la API corre como usuario **no-root**. `api/entrypoint.sh` aplica
  `alembic upgrade head` antes de arrancar.

## Gotchas

- `VITE_API_BASE_URL` se **hornea en tiempo de build** del bundle web. En Dokploy debe ser el
  dominio público de la API, nunca `localhost`.
- El `package-lock.json` de la web se **borra** dentro del Dockerfile: el lock generado en arm64
  solo fija los binarios opcionales de Rollup de esa arquitectura y `vite build` muere en x64
  (npm/cli#4828). No lo "arregles" restaurándolo.
- Las imágenes de web dev (node+vite) y prod (nginx) usan **tags distintos** a propósito, para
  que construir un entorno no pise el otro.
- El móvil declara `usesCleartextTraffic=true` solo para permitir `http://` contra un backend
  local; contra el servidor desplegado va por HTTPS.
- El STT sin red necesita el paquete de idioma **es-CO** descargado en el dispositivo; el
  fallback manual siempre cubre ese caso.
- `CORS_ORIGINS` (coma-separado) debe incluir el origen de la web, o el navegador bloquea todo.
