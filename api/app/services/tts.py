"""Generación de audio TTS (ElevenLabs) con dedup + caché permanente.

Estrategia (decidida con el usuario): ON-DEMAND al asignar un listado, deduplicado
por descripción normalizada y cacheado para siempre. Sin API key, degrada con
gracia usando un mp3 de silencio (el flujo sigue siendo demostrable).

Se sintetiza la FRASE COMPLETA de confirmación por descripción única (la unidad es
determinística por descripción en el dataset), lo que simplifica el móvil (un clip).
"""
import hashlib
import logging
from pathlib import Path

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import AudioAsset, EstadoAudio, Item, ListadoItem
from app.util import frase_confirmacion

log = logging.getLogger("tts")
settings = get_settings()
SILENCE = Path(__file__).parent / "assets" / "silence.mp3"


def desc_hash(descripcion_norm: str) -> str:
    return hashlib.sha1(descripcion_norm.encode("utf-8")).hexdigest()


def _audio_dir() -> Path:
    d = Path(settings.audio_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _synth_elevenlabs(texto: str) -> bytes:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }
    payload = {
        "text": texto,
        "model_id": settings.elevenlabs_model_id,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    resp = httpx.post(url, headers=headers, json=payload, timeout=60.0)
    resp.raise_for_status()
    return resp.content


def ensure_audio_for_listado(listado_id: int) -> None:
    """Genera (si falta) y enlaza el audio de cada ítem del listado. Idempotente:
    si el asset ya está `listo` y el archivo existe, no re-sintetiza (no gasta créditos)."""
    tiene_key = bool(settings.elevenlabs_api_key and settings.elevenlabs_voice_id)
    with SessionLocal() as db:
        items = db.scalars(
            select(Item)
            .join(ListadoItem, ListadoItem.item_id == Item.id)
            .where(ListadoItem.listado_id == listado_id)
        ).all()

        for item in items:
            h = desc_hash(item.descripcion_norm)
            texto = frase_confirmacion(item.descripcion, item.unidad)
            asset = db.scalar(select(AudioAsset).where(AudioAsset.hash_descripcion == h))
            if asset is None:
                asset = AudioAsset(
                    hash_descripcion=h, descripcion=item.descripcion,
                    texto=texto, chars=len(texto), estado=EstadoAudio.pendiente,
                )
                db.add(asset)
                db.flush()

            path = _audio_dir() / f"{h}.mp3"
            if asset.estado != EstadoAudio.listo or not path.exists():
                try:
                    if tiene_key:
                        data = _synth_elevenlabs(texto)
                        asset.creditos = len(texto)
                    else:
                        data = SILENCE.read_bytes()
                        asset.creditos = 0
                    path.write_bytes(data)
                    asset.ruta_mp3 = f"{h}.mp3"
                    asset.estado = EstadoAudio.listo
                except Exception as exc:  # noqa: BLE001
                    log.warning("TTS falló para '%s': %s", item.descripcion, exc)
                    asset.estado = EstadoAudio.error

            item.audio_asset_id = asset.id
        db.commit()
