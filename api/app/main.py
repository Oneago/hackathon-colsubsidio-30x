"""Punto de entrada de la API. FastAPI genera el OpenAPI/Swagger automáticamente
(contrato estricto para web y móvil) en /docs y /openapi.json.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.routers import auth, bodegas, listados, movil, reportes, tomas, usuarios

settings = get_settings()

app = FastAPI(
    title="Inventario Hoteles Colsubsidio — API",
    description="Fuente de verdad para la toma de inventarios (web + móvil).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers de dominio.
app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(bodegas.router)
app.include_router(tomas.router)
app.include_router(listados.router)
app.include_router(movil.router)
app.include_router(reportes.router)

# Audios TTS pre-generados, servidos estáticamente para descarga del móvil.
_audio_path = Path(settings.audio_dir)
_audio_path.mkdir(parents=True, exist_ok=True)
app.mount("/audio", StaticFiles(directory=str(_audio_path)), name="audio")


@app.get("/health", tags=["infra"], summary="Estado de la API y la base de datos")
def health() -> JSONResponse:
    """Devuelve 200 si la API responde y la base de datos está accesible."""
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 — healthcheck: cualquier fallo = no sano
        db_ok = False

    status_code = 200 if db_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if db_ok else "degraded", "database": db_ok, "env": settings.app_env},
    )
