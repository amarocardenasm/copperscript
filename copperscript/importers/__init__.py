"""Registro de importadores.

=== STUB: por implementar. Tests: tests/test_importers.py ===
(Implementación comentada de referencia en la rama spike/v0.1-referencia.)

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
    raise NotImplementedError("detectar_importador(): probar cada importador en orden")


def obtener_importador(herramienta: str) -> Importador:
    """Devuelve el importador por su nombre, para cuando el usuario lo indica a mano."""
    raise NotImplementedError("obtener_importador(): buscar por nombre")
