# Sistema de toma de inventarios — Hoteles Colsubsidio (MVP)

Optimiza y hace confiable el **conteo físico de inventario** en bodegas de hotel,
**eliminando el sesgo de confirmación**: el personal de campo nunca ve la cantidad
del ERP; cuenta a ciegas y el sistema compara después.

## Contexto — Hackathon Colsubsidio × 30X · Reto 4 (Hotelería)

Este proyecto resuelve el **Reto 4 — Hotelería** del [Hackathon Colsubsidio × 30X](https://innovacion.colsubsidio.com/#hero)
(Bogotá, 22–26 de julio de 2026).

> En las bodegas de los hoteles y parques de Colsubsidio, la toma física de inventario
> depende de una **cadena de captura manual**: alguien cuenta producto por producto y lo
> anota en papel, otra persona lo digita en el sistema y otra lo revisa. Cada eslabón
> introduce errores costosos y descuadres de inventario.

**Objetivo del reto:** permitir que el personal registre el conteo **sin papel**, reduciendo
errores de digitación y descuadres. Nuestra solución va un paso más allá y ataca la causa de
fondo — el **sesgo de confirmación** — haciendo que quien cuenta lo haga **a ciegas** (sin ver
la cantidad del ERP), con captura por **voz** y **escaneo** desde una app móvil, y reconciliación
automática en la consola web.

## Arquitectura

| Componente | Stack | Rol |
|---|---|---|
| **API** | FastAPI + Uvicorn + PostgreSQL | Única fuente de verdad. Genera OpenAPI/Swagger automático (contrato para web y móvil). |
| **Web** | React (Vite) + shadcn/ui + Tailwind | Consola de administradores y supervisores *(Fase 2+)*. |
| **Móvil** | Flutter (Android) | App de campo del supernumerario *(Fase 3+)*. |

Todo el backend se levanta con **un solo comando** vía Docker Compose.

## Arranque rápido

Requisitos: Docker con Compose v2 (`docker compose`, no el binario `docker-compose`).

```bash
cp .env.example .env      # único paso manual
docker compose up         # o: make up
```

Esto deja, desde un clon limpio y sin pasos extra:
- `db` (PostgreSQL) con volumen persistente y `healthcheck`.
- `api` que **aplica migraciones Alembic al arrancar** y expone la API.
- `seed` que carga el dataset de forma **idempotente** (re-ejecutable sin duplicar).

Comprobar:
- API: http://localhost:8000/health → `{"status":"ok"}`
- Swagger: http://localhost:8000/docs
- **Consola web:** http://localhost:5173 — ingresa con el admin del seed
  (`.env`: `ADMIN_CEDULA` / `ADMIN_PASSWORD`; por defecto `1000000000` / `admin_cambia_esta_clave`).

### Atajos (Makefile)

```
make up        Levanta el stack (build + hot reload)
make down      Detiene el stack (conserva datos)
make seed      Recarga el dataset (idempotente)
make logs      Sigue logs de la API (S=db para otro servicio)
make migrate   Aplica migraciones Alembic
make test      Ejecuta las pruebas de la API
make ps        Estado de los servicios
make clean     Detiene y BORRA volúmenes (destructivo)
make prod-up   Levanta el stack en modo producción
```

## Entornos (Compose)

- `compose.yaml` — base, agnóstica de entorno.
- `compose.override.yaml` — **desarrollo** (bind mounts, hot reload, puertos publicados). Se fusiona solo con `docker compose up`.
- `compose.prod.yaml` — **producción** (imágenes construidas, sin código montado, `restart: unless-stopped`).
  ```bash
  make prod-up
  # equivale a: docker compose -f compose.yaml -f compose.prod.yaml up -d --build
  ```
  En prod: la API corre `uvicorn` **sin `--reload`** y la **web se sirve como build estático por Nginx**
  (con SPA fallback), no por el dev server de Vite. Reverse proxy + TLS quedan como pieza opcional
  a activar cuando se defina el host de despliegue (hoy: sólo local).

Toda la configuración va por variables de entorno (`.env`, versionado como `.env.example`).
`.env` está en `.gitignore`; no hay credenciales quemadas en el código. Los Dockerfiles son
**multi-stage** y la API **no corre como root**.

## Acceso del móvil a la API (dentro de Compose)

Flutter no se contenedoriza (compila a APK y corre en el dispositivo/emulador). Por defecto
consume la API desplegada; para trabajar contra la API local de Compose (que escucha en `0.0.0.0`)
se sobreescribe la URL base:

| Escenario | URL base de la API |
|---|---|
| Servidor desplegado (por defecto) | `https://syncrologix-api.macondo.page` |
| Emulador de Android (backend local) | `http://10.0.2.2:8000` |
| Dispositivo físico en la misma red | `http://<IP-LAN-del-anfitrión>:8000` (ej. `http://192.168.1.20:8000`) |

El override se inyecta por `--dart-define` (la URL nunca se escribe a mano en el código):

```bash
flutter run                                                  # servidor desplegado
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000  # backend local
```

CORS se controla con `CORS_ORIGINS` en `.env`.

## Estructura

```
├── compose.yaml / compose.override.yaml / compose.prod.yaml
├── .env.example            # plantilla de configuración (copiar a .env)
├── Makefile
├── api/                    # FastAPI
│   ├── Dockerfile          # multi-stage, no-root
│   ├── entrypoint.sh       # migra (alembic upgrade) y arranca uvicorn
│   ├── requirements.txt
│   ├── alembic.ini · migrations/
│   └── app/
│       ├── main.py         # app FastAPI + /health
│       ├── config.py       # settings desde entorno
│       ├── db.py · models.py
│       └── seed/           # carga idempotente + mapeo bodega↔stock
├── web/                    # Consola React + Vite + shadcn/ui + Tailwind
│   ├── Dockerfile          # multi-stage: dev (Vite) / runtime (Nginx)
│   └── src/
│       ├── lib/            # api client (JWT), auth context
│       ├── components/ui/  # componentes estilo shadcn
│       └── pages/          # Login, Usuarios, Inventario, Asignaciones
├── mobile/                 # App Flutter (Android) del supernumerario
│   └── lib/                # api_client, app_state, screens (login/listado/scan/conteo)
├── dataset/                # inventory.json (respuesta simulada del ERP)
└── branding/               # DESIGN.md + assets (se aplica en Fase 6)
```

## Sobre el dataset

`dataset/inventory.json` simula la respuesta del ERP: `{ meta, bodegas[48], stock{8 ubicaciones} }`,
1405 líneas de stock. Notas que condicionan el diseño (ver el plan):
- **No trae código de barras**: solo `nrArticulo` (código ERP interno), ausente en el 18%. El seed
  genera un código sintético `GEN-…` para esos ítems → 100% escaneable.
- **UoM en inglés** (`Unidad/Kilogram/Liter/Portion`) → el seed la normaliza a es-CO.
- **`stock` = cantidad ERP** (campo anti-sesgo): se almacena pero **nunca** se expone al móvil.

## Estado por fases

- [x] **Fase 0** — Andamiaje: Compose base (`db`+`api`+`seed`), `/health`, migraciones, seed idempotente.
- [x] **Fase 1** — API: auth JWT por canal, usuarios/roles/bodegas, tomas, listados con bloqueo de concurrencia, conteos con trazabilidad, esquemas móviles sin ERP (+ test de contrato) y TTS ElevenLabs on-demand con caché.
- [x] **Fase 2** — Web: login, gestión de usuarios, inventario por bodega, tomas y asignación de listados (React+Vite+shadcn/Tailwind en Compose).
- [x] **Fase 3** — Móvil (Flutter): login, descarga de listado sin ERP + audios, escaneo, audio local, STT es-CO con fallback manual, envío de conteo. Ver [`mobile/README.md`](mobile/README.md).
- [x] **Fase 4** — Web: comparación ERP vs. conteo (Δ abs/%), resaltado de críticos y exportación CSV (`/reportes/comparacion`).
- [x] **Fase 5** — Endurecimiento: BD de test aislada (`*_test`, no ensucia la demo), pruebas de seguridad/permisos (11 API + 5 Flutter), STT refinado (números compuestos es-CO), y `compose.prod` **probado** (Nginx + Uvicorn sin reload).
- [x] **Fase 6** — Branding Colsubsidio: tokens azul/amarillo/grafito de `DESIGN.md` en web y móvil, logo, y WCAG (texto oscuro sobre amarillo, foco azul).
- [x] **Fase 7** — Post-MVP: modo offline total en el móvil (SQLite local, cola de sincronización con `connectivity_plus`, resolución de conflictos y sesión offline). Ver [`mobile/README.md`](mobile/README.md).
