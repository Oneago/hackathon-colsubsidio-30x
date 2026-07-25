"""Dictado por voz (POST /movil/dictado): transcripción vía ElevenLabs STT.

No se llama a ElevenLabs de verdad: se mockea `transcribir` en el módulo del router
(así se prueba el mapeo de errores del endpoint, no el cliente HTTP de tts/stt).
"""
from app.services.stt import SttError, SttNoDisponible
from tests.conftest import auth
from tests.test_flujo import _crear_usuario


def _token_supernumerario(client, admin_token, bodega_test) -> str:
    ced, _ = _crear_usuario(client, admin_token, "supernumerario", [bodega_test])
    return client.post("/auth/login/movil", json={"cedula": ced, "password": "secret123"}).json()["access_token"]


def _audio_file() -> dict:
    return {"audio": ("dictado.m4a", b"contenido-de-prueba", "audio/m4a")}


def test_dictado_ok(client, admin_token, bodega_test, monkeypatch):
    tok = _token_supernumerario(client, admin_token, bodega_test)
    monkeypatch.setattr("app.routers.movil.transcribir", lambda *a, **k: "quince")

    r = client.post("/movil/dictado", headers=auth(tok), files=_audio_file())
    assert r.status_code == 200, r.text
    assert r.json() == {"texto": "quince"}


def test_dictado_sin_api_key_da_503(client, admin_token, bodega_test, monkeypatch):
    tok = _token_supernumerario(client, admin_token, bodega_test)

    def _sin_key(*a, **k):
        raise SttNoDisponible()

    monkeypatch.setattr("app.routers.movil.transcribir", _sin_key)

    r = client.post("/movil/dictado", headers=auth(tok), files=_audio_file())
    assert r.status_code == 503


def test_dictado_error_elevenlabs_da_502(client, admin_token, bodega_test, monkeypatch):
    tok = _token_supernumerario(client, admin_token, bodega_test)

    def _falla(*a, **k):
        raise SttError("boom")

    monkeypatch.setattr("app.routers.movil.transcribir", _falla)

    r = client.post("/movil/dictado", headers=auth(tok), files=_audio_file())
    assert r.status_code == 502


def test_dictado_rechaza_audio_demasiado_grande(client, admin_token, bodega_test, monkeypatch):
    tok = _token_supernumerario(client, admin_token, bodega_test)
    monkeypatch.setattr("app.routers.movil.MAX_AUDIO_BYTES", 10)

    r = client.post("/movil/dictado", headers=auth(tok), files=_audio_file())
    assert r.status_code == 413


def test_dictado_rechaza_canal_web(client, admin_token, bodega_test):
    ced, _ = _crear_usuario(client, admin_token, "supervisor", [bodega_test])
    tok = client.post("/auth/login/web", json={"cedula": ced, "password": "secret123"}).json()["access_token"]

    r = client.post("/movil/dictado", headers=auth(tok), files=_audio_file())
    assert r.status_code == 403
