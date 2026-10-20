"""Registro de importadores.

=== IMPLEMENTACIÓN DE REFERENCIA (rama spike/v0.1-referencia) ===

Para agregar una herramienta nueva: crear su importador y sumarlo a IMPORTADORES.
Nada más del sistema necesita cambiar (RNF5, extensible).
"""

from __future__ import annotations

from pathlib import Path

from copperscript.importers.base import Importador
from copperscript.importers.sherlock import ImportadorSherlock
from copperscript.importers.spiderfoot import ImportadorSpiderFoot

IMPORTADORES: list[Importador] = [
    ImportadorSpiderFoot(),
    ImportadorSherlock(),
]


class FormatoDesconocido(ValueError):
    """Ningún importador reconoce el archivo."""


def detectar_importador(ruta: Path) -> Importador:
    """Prueba cada importador hasta que uno reconozca el archivo."""
    for importador in IMPORTADORES:
        if importador.detectar(ruta):
            return importador
    nombres = ", ".join(i.herramienta for i in IMPORTADORES)
    raise FormatoDesconocido(f"ningún importador reconoce {ruta.name} (disponibles: {nombres})")


def obtener_importador(herramienta: str) -> Importador:
    """Devuelve el importador por su nombre, para cuando el usuario lo indica a mano."""
    for importador in IMPORTADORES:
        if importador.herramienta == herramienta.lower():
            return importador
    raise FormatoDesconocido(f"no existe un importador llamado {herramienta!r}")
