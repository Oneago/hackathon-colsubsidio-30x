"""Transcripción de voz a texto (ElevenLabs Scribe) para el dictado de cantidades.

A diferencia de `tts.py`, aquí NO hay fallback silencioso: sin API key no hay nada
razonable que transcribir, así que se distingue "no configurado" (el móvil cae de
inmediato a captura manual) de "ElevenLabs falló" (error transitorio).
"""
import httpx

from app.config import get_settings

settings = get_settings()


class SttNoDisponible(Exception):
    """No hay ELEVENLABS_API_KEY configurada."""


class SttError(Exception):
    """La llamada a ElevenLabs falló (red o respuesta de error)."""


def transcribir(audio_bytes: bytes, filename: str, content_type: str) -> str:
    if not settings.elevenlabs_api_key:
        raise SttNoDisponible()

    url = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    data = {"model_id": settings.elevenlabs_stt_model_id, "language_code": "es"}
    files = {"file": (filename, audio_bytes, content_type)}
    try:
        resp = httpx.post(url, headers=headers, data=data, files=files, timeout=30.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise SttError(str(exc)) from exc

    return (resp.json().get("text") or "").strip()
