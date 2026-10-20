"""Tests del núcleo: normalización, confianza y evidencia."""

from __future__ import annotations

from pathlib import Path

import pytest

from copperscript.core.confidence import combinar
from copperscript.core.evidence import calcular_sha256, guardar_evidencia, verificar_evidencia
from copperscript.core.models import TipoEntidad
from copperscript.core.normalize import ValorInvalido, normalizar

# --- Normalización (ADR-011) ------------------------------------------------
# pytest.mark.parametrize corre el mismo test con muchos casos. Cada tupla es
# (tipo, valor crudo, clave esperada).


@pytest.mark.parametrize(
    ("tipo", "crudo", "esperado"),
    [
        (TipoEntidad.EMAIL, " Juan.Perez@Gmail.com ", "juan.perez@gmail.com"),
        (TipoEntidad.DOMINIO, "Ejemplo.CL.", "ejemplo.cl"),
        (TipoEntidad.DOMINIO, "ñandú.cl", "xn--and-6ma2c.cl"),
        (TipoEntidad.IPV4, " 192.0.2.10", "192.0.2.10"),
        (TipoEntidad.IPV6, "2001:DB8:0:0::1", "2001:db8::1"),
        (TipoEntidad.URL, "HTTPS://GitHub.com:443/amaro_dev/#top", "https://github.com/amaro_dev"),
        (TipoEntidad.URL, "https://x.cl/buscar?q=Amaro", "https://x.cl/buscar?q=Amaro"),
        (
            TipoEntidad.CUENTA,
            "https://www.github.com/amaro_dev/",
            "https://www.github.com/amaro_dev",
        ),
        (TipoEntidad.USUARIO, "@Amaro_Dev", "amaro_dev"),
        (TipoEntidad.PERSONA, "Juan   Pérez", "Juan Pérez"),
    ],
)
def test_normalizar(tipo, crudo, esperado):
    assert normalizar(tipo, crudo) == esperado


@pytest.mark.parametrize(
    ("tipo", "crudo"),
    [
        (TipoEntidad.EMAIL, "sin-arroba.cl"),
        (TipoEntidad.IPV4, "300.1.1.1"),
        (TipoEntidad.URL, "github.com/amaro"),  # sin esquema
        (TipoEntidad.DOMINIO, "   "),
    ],
)
def test_normalizar_rechaza_valores_invalidos(tipo, crudo):
    with pytest.raises(ValorInvalido):
        normalizar(tipo, crudo)


# --- Confianza (noisy-OR) ---------------------------------------------------


def test_combinar_fuentes_independientes_suben_la_confianza():
    assert combinar([("sherlock", 0.4), ("maigret", 0.6)]) == pytest.approx(0.76)


def test_combinar_misma_fuente_no_suma():
    assert combinar([("sherlock", 0.4), ("sherlock", 0.4)]) == pytest.approx(0.4)


def test_combinar_sin_observaciones_es_cero():
    assert combinar([]) == 0.0


# --- Evidencia por contenido (ADR-004) ---------------------------------------


def test_guardar_evidencia_usa_el_hash_como_nombre_y_deduplica(tmp_path: Path):
    original = tmp_path / "captura.txt"
    original.write_text("hola copperscript", encoding="utf-8")
    carpeta = tmp_path / "evidence"

    ev1 = guardar_evidencia(carpeta, original)
    ev2 = guardar_evidencia(carpeta, original)

    assert ev1.sha256 == calcular_sha256(original) == ev2.sha256
    assert ev1.nombre_original == "captura.txt"
    assert ev1.tamano == len("hola copperscript")
    archivos = [p for p in carpeta.rglob("*") if p.is_file()]
    assert len(archivos) == 1  # guardado una sola vez
    assert archivos[0].name == ev1.sha256


def test_verificar_evidencia_detecta_alteraciones(tmp_path: Path):
    original = tmp_path / "a.txt"
    original.write_text("dato original", encoding="utf-8")
    carpeta = tmp_path / "evidence"
    ev = guardar_evidencia(carpeta, original)
    assert verificar_evidencia(carpeta, ev.sha256)

    guardado = next(p for p in carpeta.rglob("*") if p.is_file())
    guardado.write_text("dato alterado", encoding="utf-8")
    assert not verificar_evidencia(carpeta, ev.sha256)
