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
`https://syncrologix-api.oneago.com`.

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

## Flujo Git

- Todo commit se hace **directamente sobre `main`**. No crear ramas adicionales.
- Al terminar una tarea, hacer commit de los cambios y `git push origin main` inmediatamente.

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
5. **Concurrencia — exclusividad por ítem, no por bodega.** Varios listados **activos** pueden
   coexistir en la misma (toma, bodega) —uno por supernumerario, para contar en paralelo—
   siempre que sus **ítems no se solapen**. Lo impone `listados.py::_conflicto_solape`,
   serializado por `_bloquear_toma` (`pg_advisory_xact_lock(toma_id)`), que **evita** la carrera
   en vez de detectarla después; por eso el 409 puede decir **cuántos** ítems chocan, en **qué**
   listado y de **quién** — un 409 anónimo deja al supervisor sin salida. Hasta la migración
   `b6f2a41c9d3e` la regla era un solo listado activo por bodega, impuesta por el índice único
   parcial `uq_listado_activo_toma_bodega`: ese índice **ya no existe** y el código ya no captura
   `IntegrityError`. Corolario: `POST /listados` sin `item_ids` asigna solo los ítems
   **disponibles** (los que no tiene ya otro listado activo de esa toma), no todos los de la
   bodega; `bodegas.py::_items_tomados_ids` es el único criterio de "disponible" y lo comparte
   con el selector de la web (`GET /bodegas/{id}/items?toma_id=`). Sin cambios: a lo sumo una
   toma abierta por bodega.
6. **Toda asignación tiene salida.** `PATCH /listados/{id}` reasigna o cancela; sin él, un error
   al asignar obligaba a cerrar la toma entera. Corolario: cerrar una toma marca sus listados
   activos como `completado` — si no, quedan vivos para siempre, el móvil los sigue entregando y
   el supernumerario no puede recibir otra asignación.
7. **Un supernumerario, un listado vigente.** `/movil/mi-listado` entrega uno solo, así que dos
   asignaciones activas a la vez (en tomas abiertas) esconderían una. Se bloquea al asignar.
8. **Lo definitivo responde 409, no 404.** La cola offline del móvil (`resolverSync`) reintenta
   los 404 indefinidamente y marca los 409 como conflicto. Por eso `POST /movil/conteos` devuelve
   409 —no 404— cuando la toma se cerró o el listado se reasignó.
9. **Recuento libre.** Mientras la toma esté **abierta** se aceptan nuevos conteos del mismo
   ítem; cada uno incrementa `intento_num` y **vale el mayor**. Con la toma cerrada: 409.
10. **Seed idempotente.** `app/seed/seed.py` hace upsert por claves naturales
   (`bodega.id_erp` / `slug`, `item.descripcion_norm`). Correrlo N veces deja el mismo estado.
   Lo mismo aplica a la plantilla demo (`app/seed/usuarios_demo.py`, upsert por cédula): como
   corre en **cada despliegue**, reconcilia nombre/rol/bodegas pero **nunca** pisa una
   contraseña ya cambiada. Referencia las bodegas por clave natural (`slug:` / `erp:`), nunca
   por `id`: el autoincremental no coincide entre local y producción. `tests/test_usuarios_demo.py`
   verifica que el roster cumpla la regla de bodegas por rol (invariante 3).

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
- `/usuarios` (solo admin) salvo `/usuarios/supernumerarios?bodega_id=` (admin **y** supervisor,
  acotado a sus bodegas: sin ella el supervisor no puede asignar nada). Ojo con el orden de las
  rutas: va declarada antes que `/usuarios/{usuario_id}` o FastAPI la captura como id.
- `/bodegas` + `/bodegas/{id}/items` (web, **sí** incluye `cantidad_erp`), `/tomas`
  (abrir/cerrar/reabrir/listar/eliminar), `/listados` (`POST` asignar, `PATCH` reasignar/cancelar).
- Las dos salidas de la comparación, sobre una toma **cerrada**: `POST /tomas/{id}/aceptar` sella
  la aprobación (`aceptada_en`/`aceptada_por`; **no** es un valor del enum `estado_toma`, la toma
  sigue `cerrada`) y `POST /tomas/{id}/solicitar-reconteo` la reabre **y revive sus listados
  `completado`** para que vuelvan a la app de campo. Son excluyentes: reabrir o pedir reconteo
  anulan la aceptación, porque lo aprobado fue un conteo que va a cambiar. `reabrir` sigue siendo
  la versión mínima (solo corrige un cierre por error; no toca los listados).
- `/movil` (solo supernumerario): `mi-listado`, `conteos`, `dictado` (transcribe audio con
  ElevenLabs STT para el dictado de cantidad; 503 si falta la API key, 502 si ElevenLabs falla).
- `/reportes`: `comparacion` y `comparacion.csv` (Δ absoluto y %, marca de crítico según
  `DIFF_UMBRAL_PCT`, CSV con BOM para Excel). Excluye los listados **cancelados**: si no, una
  reasignación duplica cada línea del informe.
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

## Etiquetas imprimibles (`web/src/pages/Etiquetas.tsx`)

El dataset no trae códigos de barras reales, así que para demostrar el escaneo hay que
imprimirlos. `lib/code128.ts` codifica **Code 128** a mano (sin librería: la consola debe
imprimir sin CDN) y `components/CodigoBarras.tsx` lo dibuja en SVG, que la impresora rasteriza
nítido a cualquier tamaño. Subconjunto C para códigos numéricos pares (mitad de ancho), B para
el resto. La impresión se controla con `@media print` en `index.css`: `.no-imprimir` oculta la
interfaz y `.contenedor-app`/`.area-contenido` sueltan el alto fijo del layout.

Dos cosas que no se deben romper: la etiqueta **nunca** lleva `cantidad_erp` (invariante 1), y
los códigos sintéticos `GEN-<sha1>` ocupan ~189 módulos — a 4 por fila bajan de 0,25 mm por
barra y dejan de leerse, por eso la página avisa antes de imprimir.

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
- Flujo de conteo: escaneo o búsqueda → audio + frase en alto contraste → dictado (graba con
  `record`, sube el audio a `POST /movil/dictado`, la API lo transcribe con ElevenLabs STT) →
  tras **3 intentos** fallidos aparece el teclado numérico (`screens/conteo_screen.dart`). El
  parser de voz (`services/parseo_cantidad.dart`) entiende dígitos y palabras es-CO, incluidos
  compuestos ("treinta y cinco"), sin importar si el texto vino de ElevenLabs o se tipeó. El
  dictado **necesita red** (no hay motor local de respaldo): sin conexión el botón se
  deshabilita y un banner en pantalla avisa que se debe usar el teclado con cuidado extra.

## Dataset y seed

`dataset/inventory.json` simula la respuesta del ERP: 48 bodegas, 8 ubicaciones de stock,
1405 líneas. Condiciona el diseño:

- **No hay código de barras**: solo `nrArticulo`, ausente en ~18%. El seed genera un código
  sintético `GEN-<sha1[:10]>` estable → 100% escaneable.
- **UoM en inglés** (`Unidad/Kilogram/Liter/Portion`) → se normaliza al enum es-CO.
- `stock` = cantidad ERP → se guarda en `cantidad_erp` (campo anti-sesgo).
- El mapeo stock→bodega es manual y vive en `api/app/seed/bodega_stock_map.json`.

## Voz (ElevenLabs): TTS + STT

Toda la voz de la app —tanto la que se escucha como la que se dicta— pasa por la API, que es
la única que tiene `ELEVENLABS_API_KEY`. El móvil **nunca** habla directo con ElevenLabs ni usa
motores de voz nativos del dispositivo.

- **TTS** (`services/tts.py`): sintetiza **on-demand al crear un listado** (BackgroundTask),
  deduplicando por descripción normalizada y cacheando para siempre en el volumen
  `audio_store`. Sin API key degrada con gracia a un mp3 de silencio, así que el flujo sigue
  siendo demostrable. Es idempotente: no re-sintetiza lo ya generado (no quema créditos).
- **STT** (`services/stt.py`): transcribe el audio que el móvil graba al dictar una cantidad
  (`POST /movil/dictado`, modelo `ELEVENLABS_STT_MODEL_ID`/`scribe_v1`). A diferencia del TTS,
  **no** degrada a un resultado vacío sin API key: responde 503 explícito para que el móvil
  caiga de inmediato a captura manual, en vez de simular un reconocimiento que nunca llegaría.
  No hay deduplicación posible (cada dictado es audio distinto), así que cada llamada consume
  créditos — el límite de tamaño (`MAX_AUDIO_BYTES` en `routers/movil.py`) y el auto-stop de
  ~15s en el móvil existen para acotar ese costo.

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
- El dictado por voz depende de la API (ElevenLabs STT vía `/movil/dictado`): sin red no hay
  motor local de respaldo, el botón de dictar queda deshabilitado y el fallback manual siempre
  cubre ese caso.
- `CORS_ORIGINS` (coma-separado) debe incluir el origen de la web, o el navegador bloquea todo.
